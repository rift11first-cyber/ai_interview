from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "interviewiq"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERVIEWIQ_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "InterviewIQ"
    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = True

    data_dir: Path = _default_data_dir()
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dims: int = 1536

    max_resume_mb: int = 10
    max_interview_turns: int = 8
    rag_top_k: int = 6

    @property
    def db_path(self) -> Path:
        return self.data_dir / "interviewiq.db"

    @property
    def lancedb_path(self) -> Path:
        return self.data_dir / "lancedb"

    @property
    def resumes_dir(self) -> Path:
        return self.data_dir / "resumes"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
        self.lancedb_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
