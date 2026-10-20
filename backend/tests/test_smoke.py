import json
from pathlib import Path

from sqlmodel import Session, select

from interviewiq_backend.db.models import Resume
from interviewiq_backend.db.session import get_engine, init_db
from interviewiq_backend.db.seed import seed_database
from interviewiq_backend.services.resume.parser import _heuristic_parse


def test_heuristic_parse_extracts_email_and_skills():
    text = """Jane Doe
jane@college.edu
Skills: Python, React, SQL, Docker
Projects
Campus Hub
A portal for students using React and FastAPI.
"""
    parsed = _heuristic_parse(text)
    assert parsed.email == "jane@college.edu"
    assert any("Python" in s for s in parsed.skills)


def test_seed_companies():
    init_db()
    with Session(get_engine()) as session:
        seed_database(session)
        from interviewiq_backend.db.models import Company

        companies = session.exec(select(Company)).all()
        assert len(companies) >= 3
        assert session.get(Company, "amazon") is not None


def test_knowledge_seed_file_exists():
    path = Path(__file__).resolve().parents[2] / "knowledge" / "seed" / "interview_experiences.jsonl"
    # repo root is parents[1] from backend/tests -> backend, parents[2] -> rag
    path = Path(__file__).resolve().parents[1].parent / "knowledge" / "seed" / "interview_experiences.jsonl"
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) >= 5
