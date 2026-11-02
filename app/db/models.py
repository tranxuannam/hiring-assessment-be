from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScoringJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SCORED = "scored"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    external_id: Mapped[Optional[str]] = mapped_column(String(80), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidates: Mapped[list["Candidate"]] = relationship(back_populates="role")
    questions: Mapped[list["Question"]] = relationship(back_populates="role")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    external_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    role_id: Mapped[Optional[str]] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    access_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: sha256(str(uuid4()).encode()).hexdigest()
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped[Optional[Role]] = relationship(back_populates="candidates")
    answers: Mapped[list["Answer"]] = relationship(back_populates="candidate")
    scoring_jobs: Mapped[list["ScoringJob"]] = relationship(back_populates="candidate")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    external_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    role_id: Mapped[Optional[str]] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    expected_topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, default=10)
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped[Optional[Role]] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(back_populates="question")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("candidate_id", "question_id", name="uq_answer_candidate_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    candidate: Mapped[Candidate] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship(back_populates="answers")
    score: Mapped[Optional["Score"]] = relationship(back_populates="answer", uselist=False)
    scoring_jobs: Mapped[list["ScoringJob"]] = relationship(back_populates="answer")


class ScoringJob(Base):
    __tablename__ = "scoring_jobs"
    __table_args__ = (UniqueConstraint("answer_id", name="uq_scoring_job_answer"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    answer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("answers.id"), nullable=True, index=True)
    status: Mapped[ScoringJobStatus] = mapped_column(String(20), default=ScoringJobStatus.QUEUED, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    candidate: Mapped[Candidate] = relationship(back_populates="scoring_jobs")
    answer: Mapped[Optional["Answer"]] = relationship(back_populates="scoring_jobs")
    scores: Mapped[list["Score"]] = relationship(back_populates="scoring_job")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), unique=True, index=True)
    scoring_job_id: Mapped[str] = mapped_column(ForeignKey("scoring_jobs.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    max_score: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(50))
    override_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overridden_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    answer: Mapped[Answer] = relationship(back_populates="score")
    scoring_job: Mapped[ScoringJob] = relationship(back_populates="scores")
