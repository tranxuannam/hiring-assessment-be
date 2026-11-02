import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Candidate, Role
from app.services.authorization import hash_candidate_token


def create_mock_candidate(
    db: Session,
    full_name: str,
    email: str,
    role_name: str,
    settings: Settings | None = None,
) -> tuple[Candidate, str]:
    settings = settings or get_settings()
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    token = secrets.token_urlsafe(32)
    candidate = Candidate(
        role_id=role.id,
        email=email,
        full_name=full_name,
        access_token_hash=hash_candidate_token(token, settings),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate, token


def rotate_candidate_token(
    db: Session,
    candidate_id: str,
    settings: Settings | None = None,
) -> tuple[Candidate, str]:
    settings = settings or get_settings()
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise ValueError("Candidate not found")
    token = secrets.token_urlsafe(32)
    candidate.access_token_hash = hash_candidate_token(token, settings)
    db.commit()
    db.refresh(candidate)
    return candidate, token
