import json

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.api_models import AuditEvent
from app.db.models import Answer, Candidate, Role, Score


def list_candidates_grouped_by_role(db: Session) -> dict[str, list[Candidate]]:
    candidates = db.scalars(select(Candidate).options(joinedload(Candidate.role)).order_by(Candidate.full_name)).all()
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        role_name = candidate.role.name if candidate.role else "Unassigned"
        grouped.setdefault(role_name, []).append(candidate)
    return grouped


def get_candidate_answers(db: Session, candidate_id: str) -> list[Answer]:
    return db.scalars(
        select(Answer)
        .options(joinedload(Answer.question), joinedload(Answer.score))
        .where(Answer.candidate_id == candidate_id)
        .order_by(Answer.created_at)
    ).all()


def override_score(db: Session, answer_id: str, score_value: int, reason: str, actor_id: str) -> Score:
    score = db.scalar(
        select(Score).join(Answer).where(Score.answer_id == answer_id)
    )
    if score is None:
        raise ValueError("No suggested score exists for this answer")
    score.override_score = score_value
    score.override_reason = reason
    score.overridden_by = actor_id
    db.add(
        AuditEvent(
            actor_type="hr_mock",
            actor_id=actor_id,
            action="score_override",
            candidate_id=score.answer.candidate_id,
            answer_id=answer_id,
            details=json.dumps({"score": score_value, "reason": reason}),
        )
    )
    db.commit()
    db.refresh(score)
    return score


def audit_events_for_candidate(db: Session, candidate_id: str) -> list[AuditEvent]:
    return db.scalars(
        select(AuditEvent).where(AuditEvent.candidate_id == candidate_id).order_by(AuditEvent.created_at)
    ).all()
