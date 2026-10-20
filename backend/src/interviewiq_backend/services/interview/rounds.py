from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ROUND_DURATION_MINUTES = 15


def rounds_for_level(level: str, title: str = "") -> list[dict[str, Any]]:
    normalized = f"{level} {title}".lower()
    if any(term in normalized for term in ("senior", "lead", "staff")):
        names = [
            ("Technical foundations", "technical"),
            ("Technical problem solving", "technical"),
            ("System design", "technical"),
            ("Leadership and HR", "hr"),
        ]
    elif any(term in normalized for term in ("mid", "experienced")):
        names = [
            ("Technical foundations", "technical"),
            ("Technical problem solving", "technical"),
            ("System design", "technical"),
            ("Behavioral and HR", "hr"),
        ]
    else:
        names = [
            ("Technical foundations", "technical"),
            ("Technical problem solving", "technical"),
            ("HR and communication", "hr"),
        ]
    durations = [ROUND_DURATION_MINUTES] * len(names) if len(names) == 3 else [11, 11, 11, 12]
    return [
        {
            "index": index,
            "name": name,
            "type": round_type,
            "duration_minutes": durations[index - 1],
            "status": "pending",
            "score": None,
            "feedback": "",
        }
        for index, (name, round_type) in enumerate(names, start=1)
    ]


def start_rounds(level: str, title: str) -> list[dict[str, Any]]:
    rounds = rounds_for_level(level, title)
    rounds[0]["status"] = "in_progress"
    return rounds


def elapsed_seconds(started_at: str | None) -> float:
    if not started_at:
        return 0
    started = datetime.fromisoformat(started_at)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - started).total_seconds())


def round_elapsed_seconds(state: dict[str, Any], started_at: str | None) -> float:
    return max(0, elapsed_seconds(started_at) - float(state.get("completed_round_seconds", 0)))


def total_duration_minutes(state: dict[str, Any]) -> int:
    return sum(int(item["duration_minutes"]) for item in state.get("rounds", []))
