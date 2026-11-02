from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    source_directory: Mapped[str] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportedReferenceScore(Base):
    __tablename__ = "imported_reference_scores"
    __table_args__ = (UniqueConstraint("source_answer_id", name="uq_reference_score_source_answer"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_answer_id: Mapped[str] = mapped_column(String(80))
    question_id: Mapped[str] = mapped_column(String(80))
    score: Mapped[int] = mapped_column(Integer)
    scored_by: Mapped[str] = mapped_column(String(200))


class ImportedPipelineRecord(Base):
    __tablename__ = "imported_pipeline_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(80), unique=True)
    candidate_name: Mapped[str] = mapped_column(String(200))
    candidate_email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(120))
    applied_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cv_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    invited_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    answers_submitted_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outcome_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class ImportedScoringRecord(Base):
    __tablename__ = "imported_scoring_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    answer_ref: Mapped[str] = mapped_column(String(80), unique=True)
    candidate_id: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(120))
    question_id: Mapped[str] = mapped_column(String(80))
    scored_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    scorer_1: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    score_1: Mapped[int] = mapped_column(Integer)
    scorer_2: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    score_2: Mapped[int] = mapped_column(Integer)


class ImportedInboxMessage(Base):
    __tablename__ = "imported_inbox_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    received_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    from_address: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ImportedHRTimeLog(Base):
    __tablename__ = "imported_hr_time_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    week_starting: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    task: Mapped[str] = mapped_column(String(200))
    hours: Mapped[float] = mapped_column()


class ImportedAudioAsset(Base):
    __tablename__ = "imported_audio_assets"
    __table_args__ = (UniqueConstraint("source_filename", name="uq_imported_audio_filename"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
