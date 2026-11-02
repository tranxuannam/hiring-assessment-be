from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.schemas import (
    AnswerResponse,
    CandidateAccessResponse,
    CandidateAnswerRequest,
    CandidateProgressResponse,
    CandidateQuestionResponse,
)
from app.services.candidate import (
    candidate_progress,
    get_candidate_by_token,
    get_question_for_candidate,
    save_audio_answer,
    save_text_answer,
    submit_assessment,
)

router = APIRouter(prefix="/candidate", tags=["candidate"])


def _candidate_or_404(db: Session, token: str):
    try:
        return get_candidate_by_token(db, token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/{token}", response_model=CandidateAccessResponse)
def access_assessment(token: str, db: Session = Depends(get_db)) -> CandidateAccessResponse:
    candidate = _candidate_or_404(db, token)
    return CandidateAccessResponse(
        candidate_id=candidate.id,
        full_name=candidate.full_name,
        role_name=candidate.role.name if candidate.role else None,
        submitted=candidate.submitted_at is not None,
    )


@router.get("/{token}/questions/{position}", response_model=CandidateQuestionResponse)
def get_one_question(token: str, position: int, db: Session = Depends(get_db)) -> CandidateQuestionResponse:
    candidate = _candidate_or_404(db, token)
    try:
        question, answer = get_question_for_candidate(db, candidate, position)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CandidateQuestionResponse(
        id=question.id,
        position=question.position,
        prompt=question.prompt,
        answer_text=answer.answer_text if answer else None,
        has_audio=bool(answer and answer.audio_path),
        submitted=bool(answer and answer.submitted_at),
    )


@router.put("/{token}/questions/{position}/answer", response_model=AnswerResponse)
def submit_text_answer(
    token: str,
    position: int,
    payload: CandidateAnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResponse:
    candidate = _candidate_or_404(db, token)
    try:
        question, _ = get_question_for_candidate(db, candidate, position)
        answer = save_text_answer(db, candidate, question, payload.answer_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return answer


@router.post("/{token}/questions/{position}/audio", response_model=AnswerResponse)
def upload_audio_answer(
    token: str,
    position: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnswerResponse:
    candidate = _candidate_or_404(db, token)
    try:
        question, _ = get_question_for_candidate(db, candidate, position)
        content = audio.file.read()
        answer = save_audio_answer(db, candidate, question, audio.filename, content, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return answer


@router.get("/{token}/progress", response_model=CandidateProgressResponse)
def get_progress(token: str, db: Session = Depends(get_db)) -> CandidateProgressResponse:
    candidate = _candidate_or_404(db, token)
    answered, total = candidate_progress(db, candidate)
    return CandidateProgressResponse(
        answered_questions=answered,
        total_questions=total,
        submitted=candidate.submitted_at is not None,
    )


@router.post("/{token}/submit", response_model=CandidateProgressResponse)
def submit(token: str, db: Session = Depends(get_db)) -> CandidateProgressResponse:
    candidate = _candidate_or_404(db, token)
    try:
        candidate = submit_assessment(db, candidate.id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    answered, total = candidate_progress(db, candidate)
    return CandidateProgressResponse(answered_questions=answered, total_questions=total, submitted=True)
