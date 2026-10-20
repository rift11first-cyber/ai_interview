from __future__ import annotations

import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends
from sqlmodel import Session

from interviewiq_backend.api.schemas import (
    ModelInfo,
    SettingsOut,
    SettingsUpdate,
    VerifyKeyRequest,
    VerifyKeyResponse,
)
from interviewiq_backend.core.config import get_settings
from interviewiq_backend.db.models import Setting
from interviewiq_backend.db.session import get_session
from interviewiq_backend.lancedb.store import get_knowledge_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Cache the public OpenRouter model catalogue for an hour.
_MODELS_CACHE: dict = {"at": 0.0, "items": []}
_MODELS_TTL_S = 3600.0


def _get_setting(session: Session, key: str) -> str | None:
    row = session.get(Setting, key)
    return row.value_json if row else None


def _set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row:
        row.value_json = value
        session.add(row)
    else:
        session.add(Setting(key=key, value_json=value))
    session.commit()


def _overlay_from_db(session: Session) -> None:
    """Apply persisted settings onto the live Settings singleton."""
    settings = get_settings()
    key = _get_setting(session, "openrouter_api_key")
    if key:
        try:
            settings.openrouter_api_key = json.loads(key)
        except json.JSONDecodeError:
            settings.openrouter_api_key = key.strip('"')
    chat = _get_setting(session, "chat_model")
    if chat:
        settings.chat_model = json.loads(chat)
    emb = _get_setting(session, "embedding_model")
    if emb:
        settings.embedding_model = json.loads(emb)
    turns = _get_setting(session, "max_interview_turns")
    if turns:
        settings.max_interview_turns = int(json.loads(turns))


@router.get("", response_model=SettingsOut)
def get_app_settings(session: Session = Depends(get_session)) -> SettingsOut:
    _overlay_from_db(session)
    settings = get_settings()
    return SettingsOut(
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
        has_api_key=bool(settings.openrouter_api_key),
        max_interview_turns=settings.max_interview_turns,
    )


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate, session: Session = Depends(get_session)
) -> SettingsOut:
    settings = get_settings()
    if body.openrouter_api_key is not None:
        _set_setting(session, "openrouter_api_key", json.dumps(body.openrouter_api_key))
        settings.openrouter_api_key = body.openrouter_api_key
    if body.chat_model is not None:
        _set_setting(session, "chat_model", json.dumps(body.chat_model))
        settings.chat_model = body.chat_model
    if body.embedding_model is not None:
        _set_setting(session, "embedding_model", json.dumps(body.embedding_model))
        settings.embedding_model = body.embedding_model
    if body.max_interview_turns is not None:
        _set_setting(session, "max_interview_turns", json.dumps(body.max_interview_turns))
        settings.max_interview_turns = body.max_interview_turns

    if body.openrouter_api_key:
        try:
            await get_knowledge_store().ensure_seeded(force=True)
        except Exception:
            pass

    return get_app_settings(session)


@router.post("/reindex")
async def reindex_knowledge() -> dict:
    n = await get_knowledge_store().ensure_seeded(force=True)
    return {"indexed": n}


def _is_free_model(model_id: str) -> bool:
    return model_id.endswith(":free")


@router.get("/models", response_model=list[ModelInfo])
async def list_models(free_only: bool = True) -> list[ModelInfo]:
    """List OpenRouter models (free ones by default) so the UI can offer a picker.

    The catalogue endpoint is public — no API key needed.
    """
    settings = get_settings()
    now = time.monotonic()
    if _MODELS_CACHE["items"] and now - _MODELS_CACHE["at"] < _MODELS_TTL_S:
        items = _MODELS_CACHE["items"]
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{settings.openrouter_base_url}/models")
                resp.raise_for_status()
                items = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch OpenRouter models: %s", exc)
            # Serve stale cache, or a small static fallback of well-known free models.
            items = _MODELS_CACHE["items"] or [
                {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B Instruct (free)"},
                {"id": "google/gemma-3-27b-it:free", "name": "Gemma 3 27B (free)"},
                {"id": "qwen/qwen3-235b-a22b:free", "name": "Qwen3 235B (free)"},
                {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (free)"},
                {"id": "mistralai/mistral-small-3.1-24b-instruct:free", "name": "Mistral Small 3.1 (free)"},
            ]
        _MODELS_CACHE["at"] = now
        _MODELS_CACHE["items"] = items

    out: list[ModelInfo] = []
    for m in items:
        mid = str(m.get("id", ""))
        if not mid or (free_only and not _is_free_model(mid)):
            continue
        ctx = m.get("context_length")
        if ctx is None:
            ctx = (m.get("top_provider") or {}).get("context_length")
        out.append(ModelInfo(id=mid, name=str(m.get("name") or mid), context_length=ctx))
    out.sort(key=lambda m: m.name.lower())
    return out


@router.post("/verify-key", response_model=VerifyKeyResponse)
async def verify_key(body: VerifyKeyRequest) -> VerifyKeyResponse:
    """Check an OpenRouter key (provided or the stored one) without saving it."""
    settings = get_settings()
    key = (body.openrouter_api_key or settings.openrouter_api_key or "").strip()
    if not key:
        return VerifyKeyResponse(valid=False, error="No API key provided.")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/auth/key",
                headers={"Authorization": f"Bearer {key}"},
            )
        if resp.status_code == 200:
            return VerifyKeyResponse(valid=True, label=str(resp.json().get("data", {}).get("label") or ""))
        if resp.status_code in (401, 403):
            return VerifyKeyResponse(valid=False, error="Key rejected by OpenRouter (401). Check the key and try again.")
        return VerifyKeyResponse(valid=False, error=f"OpenRouter returned {resp.status_code}.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Key verification failed: %s", exc)
        return VerifyKeyResponse(valid=False, error="Could not reach OpenRouter. Check your connection and retry.")
