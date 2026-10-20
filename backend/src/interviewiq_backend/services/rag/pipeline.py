from __future__ import annotations

import json
from typing import Any, Optional

from interviewiq_backend.api.schemas import ParsedResume
from interviewiq_backend.lancedb.store import get_knowledge_store
from interviewiq_backend.services.resume.parser import resume_summary_for_prompt


async def build_rag_context(
    *,
    company_id: str,
    role_title: str,
    question_focus: str,
    resume: Optional[ParsedResume],
    top_k: int = 5,
) -> tuple[str, list[str]]:
    """Answer-aware + resume-aware retrieval.

    question_focus carries the candidate's last answer (see agent), so retrieval
    follows what the candidate just said. Resume skills/projects are appended so
    company experiences are matched against the candidate's real stack.
    """
    store = get_knowledge_store()
    resume_terms = ""
    if resume:
        bits: list[str] = []
        bits += list(resume.skills or [])[:10]
        for p in (resume.projects or [])[:3]:
            bits.append(p.name)
            bits += list(p.tech_stack or [])[:4]
        for e in (resume.experience or [])[:2]:
            if e.company:
                bits.append(e.company)
        resume_terms = " ".join(bits)[:400]
    query = f"{company_id} {role_title} interview {question_focus} {resume_terms}"
    hits = await store.search(query, company_id=company_id, top_k=top_k)

    experience_blocks = []
    ids: list[str] = []
    for h in hits:
        ids.append(str(h["id"]))
        experience_blocks.append(
            f"- [{h.get('round_type')}|{h.get('difficulty')}] {h.get('text')}"
        )

    resume_block = resume_summary_for_prompt(resume) if resume else "{}"
    context = (
        "## Candidate Resume (structured)\n"
        f"{resume_block}\n\n"
        "## Retrieved Interview Experiences\n"
        + ("\n".join(experience_blocks) if experience_blocks else "(none)")
    )
    return context, ids


def format_history(turns: list[dict[str, Any]], limit: int = 10) -> str:
    recent = turns[-limit:]
    lines = []
    for t in recent:
        q = (t.get("question_text") or "").strip()
        a = (t.get("answer_text") or "").strip()
        lines.append(f"Q{t['turn_index']}: {q}")
        if a:
            # Full answer kept (truncated only if huge) so Leo can follow up on specifics.
            lines.append(f"A{t['turn_index']}: {a[:1500]}")
    return "\n".join(lines) if lines else "(no prior turns — this is the start)"
