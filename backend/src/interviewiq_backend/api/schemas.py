from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    dates: str = ""
    gpa: Optional[str] = None


class ProjectItem(BaseModel):
    name: str
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    impact: str = ""
    highlights: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str = ""
    title: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    inferred_seniority: str = "student"


class ResumeOut(BaseModel):
    id: str
    original_filename: str
    parse_status: str
    parsed: Optional[ParsedResume] = None
    created_at: str


class CompanyOut(BaseModel):
    id: str
    name: str
    difficulty_default: str
    focus_areas: list[str]
    persona: dict[str, Any]


class RoleOut(BaseModel):
    id: str
    company_id: str
    title: str
    level: str
    skills_focus: list[str]


class RoundOut(BaseModel):
    index: int
    name: str
    type: str
    duration_minutes: int
    status: str
    score: Optional[float] = None
    feedback: str = ""


class CreateInterviewRequest(BaseModel):
    resume_id: str
    role_id: str
    mode: str = "text"


class AnswerRequest(BaseModel):
    answer_text: str


class TurnOut(BaseModel):
    id: str
    turn_index: int
    question_type: str
    question_text: str
    answer_text: Optional[str] = None
    retrieval_ids: list[str] = Field(default_factory=list)


class InterviewOut(BaseModel):
    id: str
    status: str
    company_id: str
    role_id: str
    current_turn: int
    max_turns: int
    duration_minutes: int
    elapsed_seconds: int
    current_round: int
    rounds: list[RoundOut] = Field(default_factory=list)
    mode: str
    turns: list[TurnOut] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class DimensionScore(BaseModel):
    score: float
    rationale: str
    evidence: list[str] = Field(default_factory=list)


class EvaluationOut(BaseModel):
    id: str
    session_id: str
    overall_score: float
    hiring_signal: str
    dimensions: dict[str, DimensionScore]
    summary: str
    recommendations: list[str]
    model: str
    created_at: str
    rounds: list[RoundOut] = Field(default_factory=list)


class SettingsOut(BaseModel):
    chat_model: str
    embedding_model: str
    has_api_key: bool
    max_interview_turns: int


class SettingsUpdate(BaseModel):
    chat_model: Optional[str] = None
    embedding_model: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    max_interview_turns: Optional[int] = None


class ModelInfo(BaseModel):
    id: str
    name: str
    context_length: Optional[int] = None


class VerifyKeyRequest(BaseModel):
    openrouter_api_key: Optional[str] = None


class VerifyKeyResponse(BaseModel):
    valid: bool
    label: Optional[str] = None
    error: Optional[str] = None


class HealthOut(BaseModel):
    status: str
    version: str
    data_dir: str
