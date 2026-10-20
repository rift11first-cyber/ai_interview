from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from interviewiq_backend import __version__
from interviewiq_backend.api import companies, health, interviews, resumes, settings as settings_api, voice
from interviewiq_backend.core.config import get_settings
from interviewiq_backend.core.errors import AppError, app_error_handler
from interviewiq_backend.core.logging import setup_logging
from interviewiq_backend.db.seed import seed_database
from interviewiq_backend.db.session import get_engine, init_db
from interviewiq_backend.lancedb.store import get_knowledge_store

logger = logging.getLogger(__name__)


def _load_api_key_from_db() -> None:
    from interviewiq_backend.db.models import Setting
    import json

    settings = get_settings()
    with Session(get_engine()) as session:
        row = session.get(Setting, "openrouter_api_key")
        if row:
            try:
                settings.openrouter_api_key = json.loads(row.value_json)
            except Exception:
                settings.openrouter_api_key = row.value_json.strip('"')
        chat = session.get(Setting, "chat_model")
        if chat:
            settings.chat_model = json.loads(chat.value_json)
        emb = session.get(Setting, "embedding_model")
        if emb:
            settings.embedding_model = json.loads(emb.value_json)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)
    settings.ensure_dirs()
    init_db()
    with Session(get_engine()) as session:
        seed_database(session)
    _load_api_key_from_db()
    try:
        n = await get_knowledge_store().ensure_seeded()
        logger.info("Knowledge base ready (%s chunks)", n)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Knowledge seed deferred: %s", exc)
    logger.info("InterviewIQ backend v%s listening prep on %s:%s", __version__, settings.host, settings.port)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="InterviewIQ", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(health.router)
    app.include_router(resumes.router)
    app.include_router(companies.router)
    app.include_router(interviews.router)
    app.include_router(settings_api.router)
    app.include_router(voice.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "interviewiq_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
