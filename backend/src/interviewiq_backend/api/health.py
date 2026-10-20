from __future__ import annotations

from fastapi import APIRouter

from interviewiq_backend import __version__
from interviewiq_backend.api.schemas import HealthOut
from interviewiq_backend.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        version=__version__,
        data_dir=str(settings.data_dir),
    )
