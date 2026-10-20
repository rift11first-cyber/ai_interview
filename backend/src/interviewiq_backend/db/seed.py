from __future__ import annotations

import json

from sqlmodel import Session, select

from interviewiq_backend.db.models import Company, Profile, Role, utcnow


COMPANIES = [
    {
        "id": "amazon",
        "name": "Amazon",
        "aliases": ["aws", "amazon.com"],
        "difficulty_default": "hard",
        "focus_areas": ["leadership_principles", "dsa", "system_design", "behavioral"],
        "persona": {
            "tone": "direct and principle-driven",
            "style": "Probe for Ownership, Dive Deep, and Deliver Results using STAR.",
            "followup_style": "Ask for metrics, trade-offs, and customer impact.",
        },
    },
    {
        "id": "goldman_sachs",
        "name": "Goldman Sachs",
        "aliases": ["gs", "goldman"],
        "difficulty_default": "hard",
        "focus_areas": ["markets", "problem_solving", "communication", "technical"],
        "persona": {
            "tone": "precise and high-pressure",
            "style": "Value clarity, quantitative thinking, and composure.",
            "followup_style": "Challenge assumptions and ask for structured reasoning.",
        },
    },
    {
        "id": "cognizant_ace",
        "name": "Cognizant ACE",
        "aliases": ["cognizant", "ace"],
        "difficulty_default": "medium",
        "focus_areas": ["fundamentals", "communication", "projects", "aptitude"],
        "persona": {
            "tone": "supportive but evaluative",
            "style": "Focus on fundamentals, project clarity, and communication.",
            "followup_style": "Ask simplifying explanations and basic CS concepts.",
        },
    },
    {
        "id": "google",
        "name": "Google",
        "aliases": ["alphabet"],
        "difficulty_default": "hard",
        "focus_areas": ["dsa", "system_design", "googleyness", "coding"],
        "persona": {
            "tone": "analytical and collaborative",
            "style": "Emphasize algorithms, complexity, and clear problem decomposition.",
            "followup_style": "Explore edge cases, complexity, and alternative approaches.",
        },
    },
    {
        "id": "microsoft",
        "name": "Microsoft",
        "aliases": ["msft"],
        "difficulty_default": "medium",
        "focus_areas": ["coding", "design", "behavioral", "collaboration"],
        "persona": {
            "tone": "structured and growth-oriented",
            "style": "Balance coding depth with collaboration and product sense.",
            "followup_style": "Ask about teamwork, trade-offs, and ship decisions.",
        },
    },
]

ROLES = [
    {"id": "amazon_sde_intern", "company_id": "amazon", "title": "SDE Intern", "level": "intern", "skills": ["dsa", "oop", "projects"]},
    {"id": "amazon_sde_new_grad", "company_id": "amazon", "title": "SDE I (New Grad)", "level": "new_grad", "skills": ["dsa", "system_design", "leadership_principles"]},
    {"id": "gs_analyst", "company_id": "goldman_sachs", "title": "Engineering Analyst", "level": "new_grad", "skills": ["coding", "markets", "communication"]},
    {"id": "gs_summer_analyst", "company_id": "goldman_sachs", "title": "Summer Analyst", "level": "intern", "skills": ["problem_solving", "communication"]},
    {"id": "cognizant_ace_gen", "company_id": "cognizant_ace", "title": "ACE Graduate Engineer", "level": "new_grad", "skills": ["fundamentals", "communication", "projects"]},
    {"id": "google_swe_intern", "company_id": "google", "title": "SWE Intern", "level": "intern", "skills": ["dsa", "coding"]},
    {"id": "google_swe_new_grad", "company_id": "google", "title": "SWE New Grad", "level": "new_grad", "skills": ["dsa", "system_design"]},
    {"id": "microsoft_swe_intern", "company_id": "microsoft", "title": "SWE Intern", "level": "intern", "skills": ["coding", "design"]},
    {"id": "microsoft_swe_full", "company_id": "microsoft", "title": "Software Engineer", "level": "new_grad", "skills": ["coding", "system_design", "behavioral"]},
]


def seed_database(session: Session) -> None:
    if not session.exec(select(Profile)).first():
        session.add(Profile(display_name="Student"))

    for c in COMPANIES:
        existing = session.get(Company, c["id"])
        payload = Company(
            id=c["id"],
            name=c["name"],
            aliases_json=json.dumps(c["aliases"]),
            difficulty_default=c["difficulty_default"],
            focus_areas_json=json.dumps(c["focus_areas"]),
            persona_json=json.dumps(c["persona"]),
        )
        if existing:
            existing.name = payload.name
            existing.aliases_json = payload.aliases_json
            existing.difficulty_default = payload.difficulty_default
            existing.focus_areas_json = payload.focus_areas_json
            existing.persona_json = payload.persona_json
            session.add(existing)
        else:
            session.add(payload)

    for r in ROLES:
        existing = session.get(Role, r["id"])
        payload = Role(
            id=r["id"],
            company_id=r["company_id"],
            title=r["title"],
            level=r["level"],
            skills_focus_json=json.dumps(r["skills"]),
        )
        if existing:
            existing.title = payload.title
            existing.level = payload.level
            existing.skills_focus_json = payload.skills_focus_json
            session.add(existing)
        else:
            session.add(payload)

    session.commit()
