from __future__ import annotations

import json
from typing import Any, Optional

from interviewiq_backend.api.schemas import ParsedResume
from interviewiq_backend.services.llm.openrouter import OpenRouterClient
from interviewiq_backend.services.rag.pipeline import format_history

EVAL_SYSTEM = """You are an expert interview coach evaluating a timed role-based mock interview.
Score the candidate honestly using the transcript, resume context, role level, and round results.
Return ONLY JSON:
{
  "overall_score": number (0-10),
  "hiring_signal": "needs_work"|"borderline"|"strong",
  "dimensions": {
    "technical_depth": {"score": number, "rationale": string, "evidence": string[]},
    "communication": {"score": number, "rationale": string, "evidence": string[]},
    "confidence": {"score": number, "rationale": string, "evidence": string[]},
    "project_understanding": {"score": number, "rationale": string, "evidence": string[]},
    "problem_solving": {"score": number, "rationale": string, "evidence": string[]}
  },
  "summary": string,
  "recommendations": string[]
}"""


def _heuristic_eval(turns: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [t for t in turns if (t.get("answer_text") or "").strip()]
    avg_len = (
        sum(len(t["answer_text"]) for t in answered) / max(len(answered), 1)
    )
    base = 5.0
    if avg_len > 280:
        base += 1.5
    elif avg_len > 140:
        base += 0.8
    if len(answered) >= 5:
        base += 0.5
    base = min(8.5, max(3.0, base))

    def dim(name: str, score: float, note: str) -> dict[str, Any]:
        return {
            "score": round(score, 1),
            "rationale": note,
            "evidence": [],
        }

    return {
        "overall_score": round(base, 1),
        "hiring_signal": "borderline" if base >= 6 else "needs_work",
        "dimensions": {
            "technical_depth": dim("technical_depth", base - 0.3, "Heuristic estimate from answer length/coverage."),
            "communication": dim("communication", base, "Heuristic estimate from response completeness."),
            "confidence": dim("confidence", base - 0.2, "Heuristic estimate."),
            "project_understanding": dim("project_understanding", base, "Heuristic estimate."),
            "problem_solving": dim("problem_solving", base - 0.4, "Heuristic estimate."),
        },
        "summary": (
            "Offline heuristic evaluation (no API key). "
            "Add an OpenRouter key for detailed LLM feedback."
        ),
        "recommendations": [
            "Practice STAR answers with measurable impact.",
            "Deepen one resume project: trade-offs, metrics, failure modes.",
            "Rehearse fundamentals relevant to the selected role and seniority.",
        ],
    }


async def evaluate_interview(
    *,
    company_name: str,
    role_title: str,
    resume: Optional[ParsedResume],
    turns: list[dict[str, Any]],
    rounds: Optional[list[dict[str, Any]]] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    client = OpenRouterClient()
    if not client.api_key:
        return _heuristic_eval(turns), {"model": "heuristic", "usage": {}}

    payload = {
        "role": role_title,
        "rounds": rounds or [],
        "resume": resume.model_dump() if resume else {},
        "transcript": format_history(turns, limit=20),
    }
    messages = [
        {"role": "system", "content": EVAL_SYSTEM},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]
    try:
        data, meta = await client.chat_json(messages, temperature=0.2)
        # Normalize required keys
        if "dimensions" not in data:
            data = _heuristic_eval(turns)
            meta = {"model": "heuristic-fallback", "usage": {}}
        return data, meta
    except Exception:
        return _heuristic_eval(turns), {"model": "heuristic-fallback", "usage": {}}
