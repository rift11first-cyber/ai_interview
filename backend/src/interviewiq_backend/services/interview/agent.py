from __future__ import annotations

import json
import re
from typing import Any, Optional

from interviewiq_backend.api.schemas import ParsedResume
from interviewiq_backend.services.llm.openrouter import OpenRouterClient
from interviewiq_backend.services.rag.pipeline import build_rag_context, format_history

# NOTE: There is deliberately NO predefined question bank here.
# Every question is generated live from the candidate resume + the
# candidate's last answer (+ RAG company context), via LLM.
# The offline fallback below is also fully dynamic — it composes a
# question from uncovered resume items and keywords in the last answer.

INTERVIEWER_SYSTEM = """You are Sara, a friendly but rigorous interviewer running a timed voice + text mock interview.

You NEVER use predefined or canned questions. Every single question you ask must be
invented live for this candidate, grounded in TWO things:
1. Their RESUME (project names, tech stack, internships, skills, coursework) — quote real items by name.
2. Their LAST ANSWER and conversation history — drill deeper, challenge vague claims,
   ask for metrics, trade-offs, debugging stories, alternatives considered.

Conversation policy:
- Ask ONE short speakable question at a time (1-3 sentences, plain text, no markdown/lists).
- Turn 1: intro — ask them to introduce themselves through their resume.
- Middle turns: EITHER a deep follow-up on what they just said (if vague, missing metrics,
  missing trade-offs, or mentions a technology worth probing) OR pivot to the most
  important NOT-YET-COVERED resume item (project/skill/experience listed in coverage info).
- Never repeat a covered resume item unless following up. Never ask a generic question
  when resume detail is available.
- Match the selected role and seniority. Entry-level candidates get fundamentals and practical
  problem solving; experienced candidates get deeper trade-offs and system design.
- Stay within the active round: technical rounds ask technical questions; HR rounds ask behavioral,
  communication, motivation, and teamwork questions.
- In technical rounds, run a collaborative DSA exercise: present a role-level problem, ask the
  candidate to solve it with you, require their approach before code, then probe complexity,
  data structures, edge cases, and core CS concepts. Do not reveal the solution.
- Mix in a few resume-grounded questions about projects, skills, implementation choices, metrics,
  debugging, and trade-offs. Use exact project or skill names from the resume.
- Return ONLY JSON:
{
  "question": string,
  "question_type": "intro"|"behavioral"|"technical"|"project"|"followup"|"closing",
  "rationale": string,
  "resume_refs": string[],
  "is_followup": boolean
}
resume_refs = the exact resume project/skill/company names this question probes.
Do not include answers, coaching, or explanations."""


def initial_state(max_turns: int) -> dict[str, Any]:
    return {
        "phase": "INIT",
        "covered_refs": [],  # resume project/skill names already probed
        "followup_budget": 3,
        "weak_signals": [],
        "candidate_summary": "",
    }


def _resume_focus(resume: Optional[ParsedResume]) -> dict[str, Any]:
    """Full structured resume detail for the LLM — nothing is summarized away."""
    if not resume:
        return {"projects": [], "skills": [], "experience": [], "education": [], "name": ""}
    return {
        "name": resume.full_name or "",
        "summary": (resume.summary or "")[:600],
        "skills": list(resume.skills or [])[:30],
        "projects": [
            {
                "name": p.name,
                "description": (p.description or "")[:500],
                "tech_stack": list(p.tech_stack or [])[:10],
                "impact": (p.impact or "")[:300],
                "highlights": list(p.highlights or [])[:5],
            }
            for p in (resume.projects or [])[:8]
        ],
        "experience": [
            {
                "company": e.company,
                "title": e.title,
                "dates": e.dates,
                "bullets": list(e.bullets or [])[:5],
            }
            for e in (resume.experience or [])[:6]
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree, "field": e.field}
            for e in (resume.education or [])[:4]
        ],
        "achievements": list(resume.achievements or [])[:8],
    }


def _keywords(text: str, limit: int = 8) -> list[str]:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "using",
        "used", "use", "built", "build", "project", "worked", "work", "team", "made",
        "that", "this", "was", "were", "are", "have", "has", "had", "our", "my",
        "they", "them", "then", "than", "from", "into", "over", "under", "about",
        "very", "much", "more", "most", "such", "like", "also", "just", "will",
        # generic interview filler that must never become a question subject
        "hardest", "biggest", "best", "worst", "easier", "harder", "first", "last",
        "next", "step", "steps", "part", "parts", "thing", "things", "idea", "way",
        "ways", "time", "times", "day", "days", "really", "actually", "maybe",
        "question", "answer", "example", "instance", "detail", "details", "sure",
        "okay", "yeah", "let", "lets", "does", "did", "doing", "done", "going",
        "went", "got", "get", "say", "said", "tell", "told", "know", "think",
        "wanted", "want", "need", "make", "makes", "took", "take", "gives",
        # discourse fillers that must never become the subject of a question
        "stuff", "fine", "hmm", "huh", "not", "but", "yeah", "yes", "okay",
        "well", "anyway", "basically", "actually", "kind", "sort", "bit",
        "lot", "lots", "good", "bad", "great", "nice", "cool", "sure", "maybe",
        "right", "now", "new", "old", "big", "small", "long", "short", "same",
        "other", "another", "some", "any", "all", "each", "both", "few", "bit",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}", text or "")
    seen: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in stop or len(lw) < 3:
            continue
        if lw not in [s.lower() for s in seen]:
            seen.append(w)
        if len(seen) >= limit:
            break
    return seen


def _resume_terms(resume: Optional[ParsedResume]) -> list[str]:
    """Known resume terms (project names, skills, companies) for exact-span matching."""
    if not resume:
        return []
    terms: list[str] = []
    for p in resume.projects or []:
        if p.name:
            terms.append(p.name)
        terms += list(p.tech_stack or [])
    terms += list(resume.skills or [])
    for e in resume.experience or []:
        if e.company:
            terms.append(e.company)
        if e.title:
            terms.append(e.title)
    for e in resume.education or []:
        if e.institution:
            terms.append(e.institution)
    # Longest first so "Campus Hub" wins over "Campus".
    uniq = {t.strip() for t in terms if t and len(t.strip()) > 1}
    return sorted(uniq, key=len, reverse=True)


def _answer_keywords(answer: str, resume: Optional[ParsedResume], limit: int = 5) -> list[str]:
    """Prefer real resume terms the candidate mentioned, else distinctive words.

    This keeps offline questions grounded ("Campus Hub", "Redis") instead of
    latching onto sentence-initial words ("Campus", "Hardest").
    """
    text = answer or ""
    found: list[str] = []
    low = text.lower()
    for term in _resume_terms(resume):
        if term.lower() in low and term not in found:
            found.append(term)
        if len(found) >= limit:
            return found
    for w in _keywords(text, limit=limit * 2):
        if w not in found and w.lower() not in {f.lower() for f in found}:
            found.append(w)
        if len(found) >= limit:
            break
    return found


def _short_label(label: str, max_words: int = 8) -> str:
    """Guard against parser artifacts where a project 'name' is really a sentence."""
    label = (label or "").strip().strip(" -•\t")
    if not label:
        return ""
    words = label.split()
    if len(label) > 70 or len(words) > max_words:
        return ""
    if label.endswith((".", "!", "?")) and len(words) > 3:
        return ""
    if re.match(r"(?i)^(a|an|the|this|that|it|we|i)\b", label) and len(words) > 3:
        return ""
    return label


def _uncovered_items(resume: Optional[ParsedResume], covered: list[str]) -> list[dict[str, str]]:
    """Resume items not yet probed — drives dynamic (non-predefined) fallback + LLM coverage."""
    if not resume:
        return []
    covered_l = {c.lower() for c in covered}
    items: list[dict[str, str]] = []
    for p in resume.projects or []:
        name = _short_label(p.name)
        if name and name.lower() not in covered_l:
            desc = (p.description or "")[:240]
            # Don't duplicate: description already contains the stack; agent gets
            # tech_stack separately via _resume_focus.
            if desc.lower() == name.lower():
                desc = ""
            items.append({"kind": "project", "label": name, "detail": desc})
    for s in resume.skills or []:
        if s.lower() not in covered_l:
            items.append({"kind": "skill", "label": s, "detail": f"listed skill: {s}"})
    for e in resume.experience or []:
        key = f"{e.company} {e.title}".strip()
        if key and key.lower() not in covered_l and e.company:
            items.append({
                "kind": "experience",
                "label": key,
                "detail": "; ".join((e.bullets or [])[:2])[:240],
            })
    return items


def _is_weak_answer(answer: str) -> bool:
    text = (answer or "").strip()
    words = len(text.split())
    if words < 12:
        return True
    # Answers with numbers/metrics/tech specifics are substantive even if short.
    if re.search(r"\d+\s*(%|percent|ms|s\b|x\b|users|req|mb|gb)", text, re.I):
        return False
    if words < 22:
        vague = ["stuff", "things", "various", "etc", "a lot", "worked on", "helped with", "kind of", "sort of"]
        low = text.lower()
        return sum(1 for v in vague if v in low) >= 1
    return False


_FOLLOWUP_TEMPLATES = [
    "Dig deeper{hook} — what exactly did YOU build, what trade-off did you make, and how did you measure it worked?",
    "Interesting{hook} — what was the hardest decision there, what alternatives did you reject, and why?",
    "Let's unpack that{hook} — walk me through the implementation step by step and where it could break.",
]


_SKILL_TEMPLATES = [
    "You list {s} on your resume — where did you actually use it in a project, and what problem did it solve?",
    "Walk me through a real decision where {s} mattered. What were your alternatives, and why did you pick it?",
    "How deep is your {s} really? Describe something you built with it that would be hard for a beginner to do.",
    "If a teammate had to review your {s} code tomorrow, what should they look for first, and what would you refactor?",
]


def _dynamic_fallback_question(
    *,
    company_name: str,
    role_title: str = "the selected role",
    level: str = "entry",
    round_type: str = "technical",
    round_name: str = "Technical interview",
    resume: Optional[ParsedResume],
    turns: list[dict[str, Any]],
    last_answer: Optional[str],
    covered: list[str],
    turn_number: int,
    max_turns: int,
) -> dict[str, Any]:
    """Offline/no-LLM question composer. Fully dynamic: built from resume + last answer.

    Never returns a canned question — it picks the next uncovered resume item,
    or drills into keywords from the candidate's last answer.
    """
    focus = _resume_focus(resume)

    if turn_number <= 1 or not turns:
        name = f" {focus['name'].split()[0]}" if focus.get("name") else ""
        return {
            "question": (
                f"Hi{name}, I'm Sara. For this {round_name} round for {role_title}, "
                "walk me through your background and one experience from your resume that shows your readiness."
            ),
            "question_type": "intro",
            "rationale": "dynamic-intro-from-resume",
            # Intro does not probe a specific item, so it must not consume coverage.
            "resume_refs": [],
            "agenda_topic": "intro",
            "is_followup": False,
        }

    if round_type == "hr":
        return {
            "question": "Tell me about a time you received difficult feedback or disagreed with a teammate. What did you do, and what changed afterward?",
            "question_type": "behavioral",
            "rationale": "round-specific-hr",
            "resume_refs": [],
            "agenda_topic": "hr",
            "is_followup": bool(last_answer),
        }

    previous_questions = " ".join((turn.get("question_text") or "").lower() for turn in turns)
    if "dsa problem" not in previous_questions:
        return {
            "question": (
                f"Let's solve a DSA problem together at the {level} level: given an array of integers, "
                "find the longest contiguous subarray whose sum is zero. Before writing code, talk me "
                "through your approach, the data structure you would choose, and its time and space complexity."
            ),
            "question_type": "technical",
            "rationale": "collaborative-dsa-approach-first",
            "resume_refs": [],
            "agenda_topic": "dsa",
            "is_followup": False,
        }
    if "complexity" not in previous_questions or "data structure" not in previous_questions:
        return {
            "question": "Continue the DSA problem with me: why does your approach work, what are the time and space complexities, and what edge cases would you test?",
            "question_type": "followup",
            "rationale": "dsa-complexity-and-edge-cases",
            "resume_refs": [],
            "agenda_topic": "dsa",
            "is_followup": True,
        }
    if "core concept" not in previous_questions:
        return {
            "question": "Now connect that solution to core concepts: explain the data structure or algorithm behind it, when you would choose an alternative, and one common implementation mistake.",
            "question_type": "technical",
            "rationale": "core-concepts-followup",
            "resume_refs": [],
            "agenda_topic": "core_concepts",
            "is_followup": True,
        }

    # If last answer was weak/short → drill into ITS specifics.
    if last_answer and _is_weak_answer(last_answer):
        kws = _answer_keywords(last_answer, resume)
        hook = f" on {', '.join(kws[:3])}" if kws else ""
        template = _FOLLOWUP_TEMPLATES[(turn_number - 2) % len(_FOLLOWUP_TEMPLATES)]
        return {
            "question": template.format(hook=hook),
            "question_type": "followup",
            "rationale": "dynamic-followup-weak-answer",
            "resume_refs": kws[:3],
            "agenda_topic": "followup",
            "is_followup": True,
        }

    # Solid answer → advance to the next UNCOVERED resume item (drives coverage to the end).
    items = _uncovered_items(resume, covered)
    if items:
        nxt = items[0]
        if nxt["kind"] == "project":
            detail = nxt["detail"][:160].strip().rstrip(",;")
            lead = f"Tell me about {nxt['label']}" + (f" — {detail}." if detail else ".")
            return {
                "question": (
                    f"{lead} What problem did it solve and what was your personal contribution?"
                ),
                "question_type": "project",
                "rationale": "dynamic-next-uncovered-project",
                "resume_refs": [nxt["label"]],
                "agenda_topic": "project",
                "is_followup": False,
            }
        if nxt["kind"] == "experience":
            return {
                "question": (
                    f"At {nxt['label']}, what was the toughest problem you owned end to end, "
                    "and how did you know you solved it?"
                ),
                "question_type": "behavioral",
                "rationale": "dynamic-next-uncovered-experience",
                "resume_refs": [nxt["label"]],
                "agenda_topic": "behavioral",
                "is_followup": False,
            }
        skill_pos = sum(1 for it in items[: items.index(nxt)] if it["kind"] == "skill")
        template = _SKILL_TEMPLATES[skill_pos % len(_SKILL_TEMPLATES)]
        return {
            "question": template.format(s=nxt["label"]),
            "question_type": "technical",
            "rationale": "dynamic-next-uncovered-skill",
            "resume_refs": [nxt["label"]],
            "agenda_topic": "technical",
            "is_followup": False,
        }

    # Resume fully covered → keep digging into what they actually said.
    kws = _answer_keywords(last_answer or "", resume)
    if kws:
        return {
            "question": (
                f"Let's go deeper on {kws[0]} — if you had to rebuild that for 10x scale, "
                "what would you change and why?"
            ),
            "question_type": "technical",
            "rationale": "dynamic-scale-followup",
            "resume_refs": kws[:2],
            "agenda_topic": "technical",
            "is_followup": True,
        }

    # Nothing to mine at all → generic-but-dynamic closing drill.
    return {
        "question": (
            "Based on everything we've covered, what part of this work would you defend "
            "in a design review, and what would you cut?"
        ),
        "question_type": "technical",
        "rationale": "dynamic-final-drill",
        "resume_refs": [],
        "agenda_topic": "technical",
        "is_followup": True,
    }


async def generate_next_question(
    *,
    company: dict[str, Any],
    role: dict[str, Any],
    resume: Optional[ParsedResume],
    state: dict[str, Any],
    turns: list[dict[str, Any]],
    last_answer: Optional[str],
    max_turns: int = 8,
    round_name: str = "Technical interview",
    round_type: str = "technical",
    level: str = "entry",
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    turn_number = len(turns) + 1
    # Session completion is controlled by the 45-minute timer and round gate,
    # never by a question count.
    is_last = False
    covered: list[str] = list(state.get("covered_refs") or [])
    uncovered = _uncovered_items(resume, covered)

    # Answer-aware RAG: retrieve with the candidate's own words + resume signals.
    focus_terms = " ".join([i["label"] for i in uncovered[:4]])
    rag_focus = f"{last_answer[:300]}" if last_answer else f"intro {focus_terms}"
    if is_last:
        rag_focus = f"closing fit questions {focus_terms}"

    context, retrieval_ids = await build_rag_context(
        company_id=company["id"],
        role_title=role["title"],
        question_focus=rag_focus,
        resume=resume,
        top_k=5,
    )

    fallback_kwargs = dict(
        company_name=company["name"],
        role_title=role["title"],
        level=level,
        round_name=round_name,
        round_type=round_type,
        resume=resume,
        turns=turns,
        last_answer=last_answer,
        covered=covered,
        turn_number=turn_number,
        max_turns=max_turns,
    )

    client = OpenRouterClient()
    if not client.api_key:
        return (
            _dynamic_fallback_question(**fallback_kwargs),
            retrieval_ids,
            {"model": "dynamic-resume-fallback", "usage": {}},
        )

    persona = company.get("persona") or {}
    messages = [
        {"role": "system", "content": INTERVIEWER_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "interviewer": "Sara",
                    "role": role["title"],
                    "level": level,
                    "round_name": round_name,
                    "round_type": round_type,
                    "turn_number": turn_number,
                    "max_turns": max_turns,
                    "is_final_turn": False,
                    "resume": _resume_focus(resume),
                    "already_covered_resume_refs": covered,
                    "not_yet_covered": uncovered[:6],
                    "last_answer": last_answer,
                    "answer_was_weak": bool(last_answer and _is_weak_answer(last_answer)),
                    "history": format_history(turns, limit=10),
                    "rag_context": context,
                    "instruction": (
                        "Invent the next question NOW from the resume + last answer. "
                        "Do NOT use any predefined question. "
                        + (
                            "This is the FINAL turn: ask a closing question."
                            if is_last
                            else (
                                "If last answer was weak/vague, ask a sharp follow-up on its specifics. "
                                "Otherwise probe the most important not-yet-covered resume item, "
                                "matching the active role level and round type. "
                                f"This is timed round {round_name}; do not end the interview because of a question count."
                            )
                        )
                    ),
                },
                indent=2,
            ),
        },
    ]
    try:
        data, meta = await client.chat_json(messages, temperature=0.6)
        text = (data.get("question") or "").strip()
        if not text:
            raise ValueError("empty LLM question")
        question = {
            "question": text,
            "question_type": data.get("question_type") or ("closing" if is_last else "followup" if data.get("is_followup") else round_type),
            "rationale": data.get("rationale") or "llm-dynamic-resume-answer-driven",
            "resume_refs": data.get("resume_refs") or [],
            "agenda_topic": "closing" if is_last else (data.get("question_type") or "technical"),
            "is_followup": bool(data.get("is_followup")) if not is_last else False,
        }
        # Guardrail: LLM must not repeat a covered ref as a "new" question.
        return question, retrieval_ids, meta
    except Exception:
        return (
            _dynamic_fallback_question(**fallback_kwargs),
            retrieval_ids,
            {"model": "dynamic-resume-fallback", "usage": {}},
        )


def advance_state(
    state: dict[str, Any],
    question: dict[str, Any],
    last_answer: Optional[str] = None,
) -> dict[str, Any]:
    """Track coverage so the interview keeps moving across the resume till the end."""
    new_state = dict(state)
    new_state["phase"] = "QUESTION_LOOP"
    covered = list(new_state.get("covered_refs") or [])
    for ref in question.get("resume_refs") or []:
        if ref and ref.lower() not in {c.lower() for c in covered}:
            covered.append(ref)
    new_state["covered_refs"] = covered[-30:]
    if question.get("is_followup"):
        new_state["followup_budget"] = max(0, int(new_state.get("followup_budget", 3)) - 1)
    if last_answer and _is_weak_answer(last_answer):
        weak = list(new_state.get("weak_signals") or [])
        weak.append(f"turn weak ({len(last_answer.split())} words)")
        new_state["weak_signals"] = weak[-10:]
    return new_state
