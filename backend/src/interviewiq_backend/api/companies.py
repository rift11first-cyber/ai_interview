from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from interviewiq_backend.api.schemas import CompanyOut, RoleOut
from interviewiq_backend.core.errors import AppError
from interviewiq_backend.db.models import Company, Role
from interviewiq_backend.db.session import get_session

router = APIRouter(tags=["catalog"])


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(session: Session = Depends(get_session)) -> list[CompanyOut]:
    rows = session.exec(select(Company).order_by(Company.name)).all()
    return [
        CompanyOut(
            id=c.id,
            name=c.name,
            difficulty_default=c.difficulty_default,
            focus_areas=json.loads(c.focus_areas_json or "[]"),
            persona=json.loads(c.persona_json or "{}"),
        )
        for c in rows
    ]


@router.get("/companies/{company_id}/roles", response_model=list[RoleOut])
def list_roles(company_id: str, session: Session = Depends(get_session)) -> list[RoleOut]:
    company = session.get(Company, company_id)
    if not company:
        raise AppError("Company not found", status_code=404)
    rows = session.exec(select(Role).where(Role.company_id == company_id)).all()
    return [
        RoleOut(
            id=r.id,
            company_id=r.company_id,
            title=r.title,
            level=r.level,
            skills_focus=json.loads(r.skills_focus_json or "[]"),
        )
        for r in rows
    ]


@router.get("/roles", response_model=list[RoleOut])
def list_all_roles(session: Session = Depends(get_session)) -> list[RoleOut]:
    rows = session.exec(select(Role).order_by(Role.title)).all()
    return [
        RoleOut(
            id=r.id,
            company_id=r.company_id,
            title=r.title,
            level=r.level,
            skills_focus=json.loads(r.skills_focus_json or "[]"),
        )
        for r in rows
    ]
