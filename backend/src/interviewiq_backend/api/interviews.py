from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from interviewiq_backend.api.schemas import (
    AnswerRequest,
    CreateInterviewRequest,
    EvaluationOut,
    InterviewOut,
    ParsedResume,
    TurnOut,
    DimensionScore,
)
from interviewiq_backend.core.config import get_settings
from interviewiq_backend.core.errors import AppError
from interviewiq_backend.db.models import (
    Company,
    Evaluation,
    InterviewSession,
    InterviewTurn,
    Profile,
    Resume,
    Role,
    new_id,
    utcnow,
)
from interviewiq_backend.db.session import get_session
from interviewiq_backend.services.evaluation.engine import evaluate_interview
from interviewiq_backend.services.interview.agent import (
    advance_state,
    generate_next_question,
    initial_state,
)
from interviewiq_backend.services.interview.rounds import (
    elapsed_seconds,
    round_elapsed_seconds,
    start_rounds,
    total_duration_minutes,
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _turn_out(t: InterviewTurn) -> TurnOut:
    return TurnOut(
        id=t.id,
        turn_index=t.turn_index,
        question_type=t.question_type,
        question_text=t.question_text,
        answer_text=t.answer_text,
        retrieval_ids=json.loads(t.retrieval_ids_json or "[]"),
    )


def _session_out(session: Session, s: InterviewSession) -> InterviewOut:
    turns = session.exec(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == s.id)
        .order_by(InterviewTurn.turn_index)
    ).all()
    state = json.loads(s.state_json or "{}")
    state = json.loads(s.state_json or "{}")
    rounds = state.get("rounds", [])
    return InterviewOut(
        id=s.id,
        status=s.status,
        company_id=s.company_id,
        role_id=s.role_id,
        current_turn=s.current_turn,
        max_turns=s.max_turns,
        duration_minutes=total_duration_minutes(state),
        elapsed_seconds=int(elapsed_seconds(s.started_at)),
        current_round=int(state.get("current_round", 1)),
        rounds=rounds,
        mode=s.mode,
        turns=[_turn_out(t) for t in turns],
        started_at=s.started_at,
        completed_at=s.completed_at,
    )


def _load_resume_parsed(resume: Resume) -> Optional[ParsedResume]:
    if resume.parsed_json:
        return ParsedResume.model_validate_json(resume.parsed_json)
    return None


def _company_dict(c: Company) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "persona": json.loads(c.persona_json or "{}"),
    }


def _role_dict(r: Role) -> dict:
    return {"id": r.id, "title": r.title, "level": r.level}


@router.get("", response_model=list[InterviewOut])
def list_interviews(session: Session = Depends(get_session)) -> list[InterviewOut]:
    rows = session.exec(
        select(InterviewSession).order_by(InterviewSession.created_at.desc())
    ).all()
    return [_session_out(session, s) for s in rows]


@router.post("", response_model=InterviewOut)
def create_interview(
    body: CreateInterviewRequest,
    session: Session = Depends(get_session),
) -> InterviewOut:
    settings = get_settings()
    resume = session.get(Resume, body.resume_id)
    if not resume or resume.parse_status != "ok":
        raise AppError("Valid parsed resume required", status_code=400)
    role = session.get(Role, body.role_id)
    company = session.get(Company, role.company_id) if role else None
    if not role or not company:
        raise AppError("Invalid role", status_code=400)

    profile = session.exec(select(Profile)).first()
    if not profile:
        raise AppError("No profile", status_code=400)

    max_turns = settings.max_interview_turns
    state = initial_state(max_turns)
    state["rounds"] = start_rounds(role.level, role.title)
    state["current_round"] = 1
    state["completed_round_seconds"] = 0
    s = InterviewSession(
        profile_id=profile.id,
        resume_id=resume.id,
        company_id=company.id,
        role_id=role.id,
        mode=body.mode,
        status="draft",
        max_turns=max_turns,
        state_json=json.dumps(state),
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return _session_out(session, s)


@router.get("/{session_id}", response_model=InterviewOut)
def get_interview(session_id: str, session: Session = Depends(get_session)) -> InterviewOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    return _session_out(session, s)


@router.post("/{session_id}/start", response_model=InterviewOut)
async def start_interview(
    session_id: str, session: Session = Depends(get_session)
) -> InterviewOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    if s.status not in ("draft", "abandoned"):
        return _session_out(session, s)

    resume = session.get(Resume, s.resume_id)
    company = session.get(Company, s.company_id)
    role = session.get(Role, s.role_id)
    assert resume and company and role

    state = json.loads(s.state_json or "{}")
    current_round = state.get("rounds", [{}])[state.get("current_round", 1) - 1]
    question, retrieval_ids, meta = await generate_next_question(
        company=_company_dict(company),
        role=_role_dict(role),
        resume=_load_resume_parsed(resume),
        state=state,
        turns=[],
        last_answer=None,
        max_turns=s.max_turns,
        round_name=current_round.get("name", "Technical interview"),
        round_type=current_round.get("type", "technical"),
        level=role.level,
    )
    state = advance_state(state, question, last_answer=None)
    turn = InterviewTurn(
        session_id=s.id,
        turn_index=1,
        question_type=question["question_type"],
        question_text=question["question"],
        retrieval_ids_json=json.dumps(retrieval_ids),
        llm_meta_json=json.dumps({**meta, "round_index": state.get("current_round", 1)}),
    )
    s.status = "in_progress"
    s.current_turn = 1
    s.started_at = utcnow()
    s.state_json = json.dumps(state)
    session.add(turn)
    session.add(s)
    session.commit()
    return _session_out(session, s)


@router.post("/{session_id}/answer", response_model=InterviewOut)
async def answer_interview(
    session_id: str,
    body: AnswerRequest,
    session: Session = Depends(get_session),
) -> InterviewOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    if s.status != "in_progress":
        raise AppError("Interview is not in progress", status_code=400)
    if not body.answer_text.strip():
        raise AppError("Answer cannot be empty", status_code=400)

    turns = session.exec(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == s.id)
        .order_by(InterviewTurn.turn_index)
    ).all()
    current = turns[-1] if turns else None
    if not current or current.answer_text:
        raise AppError("No open question to answer", status_code=400)

    current.answer_text = body.answer_text.strip()
    session.add(current)

    state = json.loads(s.state_json or "{}")
    current_round = state.get("current_round", 1)
    round_config = state.get("rounds", [])[current_round - 1]
    round_expired = round_elapsed_seconds(state, s.started_at) >= round_config["duration_minutes"] * 60
    total_expired = elapsed_seconds(s.started_at) >= total_duration_minutes(state) * 60

    # A timed session ends only at the deadline; round transitions are handled by the client clock.
    if total_expired:
        s.status = "completed"
        s.completed_at = utcnow()
        s.state_json = json.dumps({**json.loads(s.state_json or "{}"), "phase": "CLOSING"})
        session.add(s)
        session.commit()
        # Kick evaluation
        await _run_evaluation(session, s)
        return _session_out(session, s)

    resume = session.get(Resume, s.resume_id)
    company = session.get(Company, s.company_id)
    role = session.get(Role, s.role_id)
    assert resume and company and role

    turn_dicts = [
        {
            "turn_index": t.turn_index,
            "question_text": t.question_text,
            "answer_text": t.answer_text,
        }
        for t in turns
    ]
    # include just-saved answer
    turn_dicts[-1]["answer_text"] = current.answer_text

    question, retrieval_ids, meta = await generate_next_question(
        company=_company_dict(company),
        role=_role_dict(role),
        resume=_load_resume_parsed(resume),
        state=state,
        turns=turn_dicts,
        rounds=state.get("rounds", []),
        last_answer=current.answer_text,
        max_turns=s.max_turns,
        round_name=round_config["name"],
        round_type=round_config["type"],
        level=role.level,
    )
    state = advance_state(state, question, last_answer=current.answer_text)
    next_index = s.current_turn + 1
    nxt = InterviewTurn(
        session_id=s.id,
        turn_index=next_index,
        question_type=question["question_type"],
        question_text=question["question"],
        retrieval_ids_json=json.dumps(retrieval_ids),
        llm_meta_json=json.dumps({**meta, "round_index": state.get("current_round", 1)}),
    )
    s.current_turn = next_index
    s.state_json = json.dumps(state)
    session.add(nxt)
    session.add(s)
    session.commit()
    return _session_out(session, s)


@router.post("/{session_id}/round-complete", response_model=InterviewOut)
async def complete_round(session_id: str, session: Session = Depends(get_session)) -> InterviewOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    if s.status != "in_progress":
        return _session_out(session, s)
    state = json.loads(s.state_json or "{}")
    rounds = state.get("rounds", [])
    round_index = int(state.get("current_round", 1))
    current_round = rounds[round_index - 1]
    turns = session.exec(
        select(InterviewTurn).where(InterviewTurn.session_id == s.id).order_by(InterviewTurn.turn_index)
    ).all()
    round_turns = [t for t in turns if int(json.loads(t.llm_meta_json or "{}").get("round_index", round_index)) == round_index]
    answered = [t for t in round_turns if t.answer_text]
    average = min(10.0, max(0.0, sum(min(10, max(0, len(t.answer_text or "") / 45)) for t in answered) / max(1, len(answered))))
    passed = bool(answered) and average >= 4.5
    current_round["score"] = round(average, 1)
    current_round["status"] = "passed" if passed else "failed"
    current_round["feedback"] = "Round passed. Moving to the next round." if passed else "Round not passed. The interview stops here."
    if not passed or round_index >= len(rounds) or elapsed_seconds(s.started_at) >= total_duration_minutes(state) * 60:
        s.status = "completed"
        s.completed_at = utcnow()
        state["phase"] = "CLOSING"
        s.state_json = json.dumps(state)
        session.add(s)
        session.commit()
        await _run_evaluation(session, s)
        return _session_out(session, s)
    state["current_round"] = round_index + 1
    state["completed_round_seconds"] = sum(int(r["duration_minutes"]) * 60 for r in rounds[:round_index])
    rounds[round_index]["status"] = "in_progress"
    state["phase"] = "ROUND_TRANSITION"
    s.state_json = json.dumps(state)
    session.add(s)
    session.commit()
    return await _start_next_round(session, s)


async def _start_next_round(session: Session, s: InterviewSession) -> InterviewOut:
    resume = session.get(Resume, s.resume_id)
    role = session.get(Role, s.role_id)
    company = session.get(Company, s.company_id)
    assert resume and role and company
    state = json.loads(s.state_json or "{}")
    current_round = state["rounds"][state["current_round"] - 1]
    turns = session.exec(select(InterviewTurn).where(InterviewTurn.session_id == s.id).order_by(InterviewTurn.turn_index)).all()
    question, retrieval_ids, meta = await generate_next_question(
        company=_company_dict(company), role=_role_dict(role), resume=_load_resume_parsed(resume),
        state=state, turns=[{"turn_index": t.turn_index, "question_text": t.question_text, "answer_text": t.answer_text} for t in turns],
        last_answer=None, max_turns=s.max_turns, round_name=current_round["name"], round_type=current_round["type"], level=role.level,
    )
    state = advance_state(state, question, last_answer=None)
    next_index = s.current_turn + 1
    session.add(InterviewTurn(session_id=s.id, turn_index=next_index, question_type=question["question_type"], question_text=question["question"], retrieval_ids_json=json.dumps(retrieval_ids), llm_meta_json=json.dumps({**meta, "round_index": state["current_round"]})))
    s.current_turn = next_index
    s.state_json = json.dumps(state)
    session.add(s)
    session.commit()
    return _session_out(session, s)


@router.post("/{session_id}/complete", response_model=InterviewOut)
async def complete_interview(
    session_id: str, session: Session = Depends(get_session)
) -> InterviewOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    if s.status == "completed":
        return _session_out(session, s)
    s.status = "completed"
    s.completed_at = utcnow()
    session.add(s)
    session.commit()
    await _run_evaluation(session, s)
    return _session_out(session, s)


async def _run_evaluation(session: Session, s: InterviewSession) -> Evaluation:
    existing = session.exec(
        select(Evaluation).where(Evaluation.session_id == s.id)
    ).first()
    if existing:
        return existing

    resume = session.get(Resume, s.resume_id)
    company = session.get(Company, s.company_id)
    role = session.get(Role, s.role_id)
    turns = session.exec(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == s.id)
        .order_by(InterviewTurn.turn_index)
    ).all()
    turn_dicts = [
        {
            "turn_index": t.turn_index,
            "question_text": t.question_text,
            "answer_text": t.answer_text,
        }
        for t in turns
    ]
    state = json.loads(s.state_json or "{}")
    data, meta = await evaluate_interview(
        company_name=company.name if company else s.company_id,
        role_title=role.title if role else s.role_id,
        resume=_load_resume_parsed(resume) if resume else None,
        turns=turn_dicts,
        rounds=state.get("rounds", []),
    )
    ev = Evaluation(
        id=new_id(),
        session_id=s.id,
        scores_json=json.dumps(
            {
                "overall_score": data.get("overall_score"),
                "hiring_signal": data.get("hiring_signal"),
                "dimensions": data.get("dimensions"),
            }
        ),
        feedback_json=json.dumps({"summary": data.get("summary", "")}),
        recommendations_json=json.dumps(data.get("recommendations") or []),
        model=str(meta.get("model", "unknown")),
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


@router.get("/{session_id}/evaluation", response_model=EvaluationOut)
async def get_evaluation(
    session_id: str, session: Session = Depends(get_session)
) -> EvaluationOut:
    s = session.get(InterviewSession, session_id)
    if not s:
        raise AppError("Interview not found", status_code=404)
    ev = session.exec(
        select(Evaluation).where(Evaluation.session_id == session_id)
    ).first()
    if not ev:
        if s.status != "completed":
            raise AppError("Interview not completed yet", status_code=400)
        ev = await _run_evaluation(session, s)

    scores = json.loads(ev.scores_json)
    feedback = json.loads(ev.feedback_json)
    recs = json.loads(ev.recommendations_json)
    dims_raw = scores.get("dimensions") or {}
    dimensions = {
        k: DimensionScore(
            score=float(v.get("score", 0)),
            rationale=v.get("rationale", ""),
            evidence=v.get("evidence") or [],
        )
        for k, v in dims_raw.items()
    }
    return EvaluationOut(
        id=ev.id,
        session_id=ev.session_id,
        overall_score=float(scores.get("overall_score") or 0),
        hiring_signal=str(scores.get("hiring_signal") or "needs_work"),
        dimensions=dimensions,
        summary=feedback.get("summary", ""),
        recommendations=recs,
        model=ev.model,
        created_at=ev.created_at,
        rounds=json.loads(s.state_json or "{}").get("rounds", []),
    )
