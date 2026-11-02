from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import ScoringJobStatus


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None


class RoleResponse(RoleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class CandidateCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role_id: Optional[str] = None


class CandidateResponse(CandidateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=1)
    expected_topics: Optional[str] = None
    max_score: int = Field(default=10, ge=1)
    position: int = Field(ge=0)
    role_id: Optional[str] = None


class QuestionResponse(QuestionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class AnswerCreate(BaseModel):
    candidate_id: str
    question_id: str
    answer_text: str = Field(min_length=1)


class AnswerResponse(AnswerCreate):
    model_config = ConfigDict(from_attributes=True)
    answer_text: str
    id: str
    created_at: datetime
    updated_at: datetime


class ScoringJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    candidate_id: str
    answer_id: Optional[str]
    status: ScoringJobStatus
    attempts: int
    last_error: Optional[str]
    available_at: datetime
    created_at: datetime
    updated_at: datetime


class ScoreCreate(BaseModel):
    answer_id: str
    scoring_job_id: str
    score: int = Field(ge=0)
    max_score: int = Field(ge=1)
    feedback: str
    reason: str = Field(min_length=1)
    model_name: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=50)


class ScoreResponse(ScoreCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    environment: str


class SchemaResponse(BaseModel):
    tables: dict[str, list[str]]


class CandidateAccessResponse(BaseModel):
    candidate_id: str
    full_name: str
    role_name: Optional[str]
    submitted: bool


class CandidateQuestionResponse(BaseModel):
    id: str
    position: int
    prompt: str
    answer_text: Optional[str]
    has_audio: bool
    submitted: bool


class CandidateAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=100_000)


class CandidateProgressResponse(BaseModel):
    answered_questions: int
    total_questions: int
    submitted: bool


class HRMockSignInRequest(BaseModel):
    label: str = Field(default="HR mock user", min_length=1, max_length=100)


class HRMockSignInResponse(BaseModel):
    mode: str
    token: str
    warning: str


class MockCandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role_name: str = Field(min_length=1, max_length=120)


class MockCandidateResponse(BaseModel):
    candidate_id: str
    full_name: str
    email: EmailStr
    role_name: str
    token: str
    assessment_link: str


class PersonalLinkResponse(BaseModel):
    candidate_id: str
    token: str
    assessment_link: str


class CandidateSummary(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role_name: Optional[str]
    submitted: bool


class HRAnswerResponse(BaseModel):
    answer_id: str
    candidate_id: str
    question_id: str
    question: str
    answer_text: str
    has_audio: bool
    suggested_score: Optional[int]
    suggested_reason: Optional[str]
    final_score: Optional[int]
    override_reason: Optional[str]
    scoring_status: Optional[ScoringJobStatus] = None
    scoring_error: Optional[str] = None


class ScoreOverrideRequest(BaseModel):
    score: int = Field(ge=1, le=4)
    reason: str = Field(min_length=1, max_length=4000)
