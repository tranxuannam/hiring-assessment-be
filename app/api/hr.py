from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.api_models import AuditEvent
from app.db.session import get_db
from app.schemas import (
    CandidateSummary,
    HRAnswerResponse,
    HRMockSignInRequest,
    HRMockSignInResponse,
    MockCandidateCreate,
    MockCandidateResponse,
    PersonalLinkResponse,
    ScoreOverrideRequest,
)
from app.services.authorization import require_hr_mock_token
from app.services.hr import (
    audit_events_for_candidate,
    get_candidate_answers,
    list_candidates_grouped_by_role,
    override_score,
)
from app.services.mock_data import create_mock_candidate, rotate_candidate_token

router = APIRouter(prefix="/hr", tags=["hr"])


@router.post("/mock-sign-in", response_model=HRMockSignInResponse)
def mock_sign_in(
    payload: HRMockSignInRequest,
    settings: Settings = Depends(get_settings),
) -> HRMockSignInResponse:
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Mock sign-in is disabled in production")
    return HRMockSignInResponse(
        mode="mock",
        token=settings.hr_mock_token,
        warning="Mock sign-in only. Do not use this authentication method in production.",
    )


@router.post("/mock-candidates", response_model=MockCandidateResponse, status_code=201)
def create_mock_candidate_endpoint(
    payload: MockCandidateCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
    settings: Settings = Depends(get_settings),
) -> MockCandidateResponse:
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Mock candidate creation is disabled in production")
    candidate, token = create_mock_candidate(
        db,
        full_name=payload.full_name,
        email=str(payload.email),
        role_name=payload.role_name,
        settings=settings,
    )
    return MockCandidateResponse(
        candidate_id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        role_name=payload.role_name,
        token=token,
        assessment_link=f"http://localhost:3000/candidate/{token}",
    )


@router.post("/candidates/{candidate_id}/personal-link", response_model=PersonalLinkResponse)
def rotate_personal_link(
    candidate_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
    settings: Settings = Depends(get_settings),
) -> PersonalLinkResponse:
    try:
        candidate, token = rotate_candidate_token(db, candidate_id, settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PersonalLinkResponse(
        candidate_id=candidate.id,
        token=token,
        assessment_link=f"http://localhost:3000/candidate/{token}",
    )


@router.get("/candidates", response_model=dict[str, list[CandidateSummary]])
def list_candidates(
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
) -> dict[str, list[CandidateSummary]]:
    grouped = list_candidates_grouped_by_role(db)
    return {
        role: [
            CandidateSummary(
                id=candidate.id,
                full_name=candidate.full_name,
                email=candidate.email,
                role_name=role if role != "Unassigned" else None,
                submitted=candidate.submitted_at is not None,
            )
            for candidate in candidates
        ]
        for role, candidates in grouped.items()
    }


@router.get("/candidates/{candidate_id}/answers", response_model=list[HRAnswerResponse])
def candidate_answers(
    candidate_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
) -> list[HRAnswerResponse]:
    answers = get_candidate_answers(db, candidate_id)
    if not answers:
        from app.db.models import Candidate

        if db.get(Candidate, candidate_id) is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
    return [
        HRAnswerResponse(
            answer_id=answer.id,
            candidate_id=answer.candidate_id,
            question_id=answer.question_id,
            question=answer.question.prompt,
            answer_text=answer.answer_text,
            has_audio=bool(answer.audio_path),
            suggested_score=answer.score.score if answer.score else None,
            suggested_reason=answer.score.reason if answer.score else None,
            final_score=(answer.score.override_score if answer.score and answer.score.override_score is not None else answer.score.score if answer.score else None),
            override_reason=answer.score.override_reason if answer.score else None,
            scoring_status=answer.scoring_jobs[-1].status if answer.scoring_jobs else None,
            scoring_error=answer.scoring_jobs[-1].last_error if answer.scoring_jobs else None,
        )
        for answer in answers
    ]


@router.post("/answers/{answer_id}/override", response_model=HRAnswerResponse)
def override_answer_score(
    answer_id: str,
    payload: ScoreOverrideRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(require_hr_mock_token),
) -> HRAnswerResponse:
    try:
        score = override_score(db, answer_id, payload.score, payload.reason, actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    answer = score.answer
    return HRAnswerResponse(
        answer_id=answer.id,
        candidate_id=answer.candidate_id,
        question_id=answer.question_id,
        question=answer.question.prompt,
        answer_text=answer.answer_text,
        has_audio=bool(answer.audio_path),
        suggested_score=score.score,
        suggested_reason=score.reason,
        final_score=score.override_score,
        override_reason=score.override_reason,
        scoring_status=answer.scoring_jobs[-1].status if answer.scoring_jobs else None,
        scoring_error=answer.scoring_jobs[-1].last_error if answer.scoring_jobs else None,
    )


@router.get("/candidates/{candidate_id}/audit", response_model=list[dict])
def candidate_audit(
    candidate_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
) -> list[dict]:
    events = audit_events_for_candidate(db, candidate_id)
    return [
        {
            "id": event.id,
            "action": event.action,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "answer_id": event.answer_id,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in events
    ]
