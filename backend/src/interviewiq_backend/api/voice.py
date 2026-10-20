from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str = ""
    voice_rate: float = 1.0


class SpeakResponse(BaseModel):
    original: str
    speakable: str
    # Hints for the browser SpeechSynthesis frontend (Sara's voice).
    voice_hints: dict = {}


def to_speakable(text: str) -> str:
    """Make LLM question text safe for TTS: strip markdown, collapse whitespace."""
    t = text or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"[#*_`>|]", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Keep questions short for voice; hard cap so the browser doesn't ramble.
    if len(t) > 600:
        t = t[:597].rsplit(" ", 1)[0] + "…"
    return t


@router.get("/config")
def voice_config() -> dict:
    return {
        "interviewer_name": "Sara",
        # Browser-native voice I/O (no server GPU needed). Future: Faster-Whisper + Piper/Kokoro.
        "input_modes": ["voice", "text", "voice+text"],
        "output_modes": ["voice", "text", "voice+text"],
        "stt": {"provider": "browser-web-speech-api", "lang": "en-US", "interim_results": True},
        "tts": {
            "provider": "browser-speech-synthesis",
            "lang": "en-US",
            "rate": 1.0,
            "pitch": 1.0,
            "note": "Frontend speaks Sara's question text via speechSynthesis; text is always shown too.",
        },
    }


@router.post("/speak", response_model=SpeakResponse)
def speak(body: SpeakRequest) -> SpeakResponse:
    clean = to_speakable(body.text)
    return SpeakResponse(
        original=body.text,
        speakable=clean,
        voice_hints={"lang": "en-US", "rate": body.voice_rate or 1.0, "pitch": 1.0},
    )
