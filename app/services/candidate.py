from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.db.api_models import AuditEvent
from app.db.models import Answer, Candidate, Question
from app.services.authorization import hash_candidate_token
from app.services.scoring import enqueue_scoring_job


def get_candidate_by_token(db: Session, token: str) -> Candidate:
    candidate = db.scalar(
        select(Candidate)
        .options(joinedload(Candidate.role))
        .where(Candidate.access_token_hash == hash_candidate_token(token))
    )
    if candidate is None:
        raise ValueError("Invalid candidate link")
    return candidate


def get_question_for_candidate(db: Session, candidate: Candidate, position: int) -> tuple[Question, Answer | None]:
    question = db.scalar(
        select(Question)
        .where(Question.role_id == candidate.role_id, Question.position == position)
    )
    if question is None:
        raise ValueError("Question not found")
    answer = db.scalar(
        select(Answer).where(Answer.candidate_id == candidate.id, Answer.question_id == question.id)
    )
    return question, answer


def save_text_answer(db: Session, candidate: Candidate, question: Question, answer_text: str) -> Answer:
    if candidate.submitted_at is not None:
        raise PermissionError("Assessment has already been submitted")
    answer = db.scalar(
        select(Answer).where(Answer.candidate_id == candidate.id, Answer.question_id == question.id)
    )
    if answer is None:
        answer = Answer(candidate_id=candidate.id, question_id=question.id, answer_text=answer_text)
        db.add(answer)
    else:
        answer.answer_text = answer_text
    db.commit()
    db.refresh(answer)
    return answer


def save_audio_answer(
    db: Session,
    candidate: Candidate,
    question: Question,
    filename: str | None,
    content: bytes,
    settings: Settings | None = None,
) -> Answer:
    if candidate.submitted_at is not None:
        raise PermissionError("Assessment has already been submitted")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Audio file exceeds the 10 MB limit")
    if not content:
        raise ValueError("Audio file is empty")
    extension = Path(filename or "").suffix.lower()
    if extension not in {".mp3", ".wav", ".m4a", ".webm", ".ogg"}:
        raise ValueError("Unsupported audio file type")
    settings = settings or get_settings()
    upload_dir = Path(settings.upload_directory)
    upload_dir.mkdir(parents=True, exist_ok=True)
    relative_path = Path(candidate.id) / f"{uuid4()}{extension}"
    target = upload_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    answer = db.scalar(
        select(Answer).where(Answer.candidate_id == candidate.id, Answer.question_id == question.id)
    )
    if answer is None:
        answer = Answer(candidate_id=candidate.id, question_id=question.id, answer_text="")
        db.add(answer)
    answer.audio_path = str(relative_path)
    db.commit()
    db.refresh(answer)
    return answer


def submit_assessment(db: Session, candidate_id: str) -> Candidate:
    submitted_at = datetime.now(timezone.utc)
    result = db.execute(
        update(Candidate)
        .where(Candidate.id == candidate_id, Candidate.submitted_at.is_(None))
        .values(submitted_at=submitted_at)
    )
    if result.rowcount != 1:
        db.rollback()
        raise PermissionError("Assessment has already been submitted")
    db.execute(
        update(Answer)
        .where(Answer.candidate_id == candidate_id, Answer.submitted_at.is_(None))
        .values(submitted_at=submitted_at)
    )
    db.add(
        AuditEvent(
            actor_type="candidate",
            actor_id=candidate_id,
            action="assessment_submitted",
            candidate_id=candidate_id,
        )
    )
    db.commit()
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise ValueError("Candidate not found")
    answer_ids = db.scalars(select(Answer.id).where(Answer.candidate_id == candidate_id)).all()
    for answer_id in answer_ids:
        enqueue_scoring_job(db, answer_id)
    return candidate


def candidate_progress(db: Session, candidate: Candidate) -> tuple[int, int]:
    total = db.scalar(select(func.count(Question.id)).where(Question.role_id == candidate.role_id)) or 0
    answered = db.scalar(
        select(func.count(Answer.id)).where(Answer.candidate_id == candidate.id)
    ) or 0
    return answered, total
