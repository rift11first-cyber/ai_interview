from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel, Column, Text


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid4())


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: str = Field(default_factory=new_id, primary_key=True)
    display_name: str = "Student"
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value_json: str = Field(sa_column=Column(Text))


class Resume(SQLModel, table=True):
    __tablename__ = "resumes"

    id: str = Field(default_factory=new_id, primary_key=True)
    profile_id: str = Field(index=True)
    original_filename: str
    file_path: str
    raw_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    parse_status: str = "pending"  # pending|ok|failed
    parsed_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: str = Field(default_factory=utcnow)


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: str = Field(primary_key=True)
    name: str
    aliases_json: str = "[]"
    difficulty_default: str = "medium"
    focus_areas_json: str = "[]"
    persona_json: str = "{}"


class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    title: str
    level: str = "new_grad"
    skills_focus_json: str = "[]"


class InterviewSession(SQLModel, table=True):
    __tablename__ = "interview_sessions"

    id: str = Field(default_factory=new_id, primary_key=True)
    profile_id: str = Field(index=True)
    resume_id: str
    company_id: str
    role_id: str
    mode: str = "text"
    status: str = "draft"  # draft|in_progress|completed|abandoned
    current_turn: int = 0
    max_turns: int = 8
    state_json: str = Field(default="{}", sa_column=Column(Text))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = Field(default_factory=utcnow)


class InterviewTurn(SQLModel, table=True):
    __tablename__ = "interview_turns"

    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(index=True)
    turn_index: int
    question_type: str
    question_text: str = Field(sa_column=Column(Text))
    answer_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    answer_audio_path: Optional[str] = None
    latency_ms: Optional[int] = None
    retrieval_ids_json: str = "[]"
    llm_meta_json: str = "{}"
    created_at: str = Field(default_factory=utcnow)


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluations"

    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(unique=True, index=True)
    scores_json: str = Field(sa_column=Column(Text))
    feedback_json: str = Field(sa_column=Column(Text))
    recommendations_json: str = Field(sa_column=Column(Text))
    model: str
    created_at: str = Field(default_factory=utcnow)


class KnowledgeSource(SQLModel, table=True):
    __tablename__ = "knowledge_sources"

    id: str = Field(default_factory=new_id, primary_key=True)
    source_url: Optional[str] = None
    source_type: str = "manual"
    company_id: Optional[str] = None
    raw_path: Optional[str] = None
    ingested_at: str = Field(default_factory=utcnow)
    license_note: str = "curated-demo"
