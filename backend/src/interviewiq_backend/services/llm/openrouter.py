from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from interviewiq_backend.core.config import Settings, get_settings
from interviewiq_backend.core.errors import AppError

logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    @property
    def api_key(self) -> str:
        return (self.settings.openrouter_api_key or "").strip()

    def require_key(self) -> str:
        key = self.api_key
        if not key:
            raise AppError(
                "OpenRouter API key not configured. Add it in Settings.",
                status_code=400,
            )
        return key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.require_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://interviewiq.local",
            "X-Title": "InterviewIQ",
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.4,
        response_json: bool = False,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.settings.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_json:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{self.settings.openrouter_base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error("OpenRouter chat error: %s", resp.text[:500])
                raise AppError(
                    f"OpenRouter chat failed ({resp.status_code})",
                    status_code=502,
                    details=resp.text[:300],
                )
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "content": content,
            "model": data.get("model", payload["model"]),
            "usage": usage,
            "raw": data,
        }

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        result = await self.chat(
            messages,
            model=model,
            temperature=temperature,
            response_json=True,
        )
        text = result["content"].strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError("LLM returned invalid JSON", status_code=502, details=str(exc))
        meta = {"model": result["model"], "usage": result["usage"]}
        return parsed, meta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.settings.embedding_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{self.settings.openrouter_base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error("OpenRouter embed error: %s", resp.text[:500])
                raise AppError(
                    f"OpenRouter embeddings failed ({resp.status_code})",
                    status_code=502,
                    details=resp.text[:300],
                )
            data = resp.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


def local_fallback_embed(texts: list[str], dims: int = 1536) -> list[list[float]]:
    """Deterministic bag-of-words hash embedding for offline demo / no API key."""
    import hashlib
    import math

    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dims
        tokens = text.lower().split()
        if not tokens:
            vectors.append(vec)
            continue
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % dims
            sign = 1.0 if (h // dims) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors
