from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, select

from interviewiq_backend.api.schemas import ParsedResume, ResumeOut
from interviewiq_backend.core.config import get_settings
from interviewiq_backend.core.errors import AppError
from interviewiq_backend.db.models import Profile, Resume, new_id, utcnow
from interviewiq_backend.db.session import get_session
from interviewiq_backend.services.resume.parser import parse_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _to_out(resume: Resume) -> ResumeOut:
    parsed = None
    if resume.parsed_json:
        parsed = ParsedResume.model_validate_json(resume.parsed_json)
    return ResumeOut(
        id=resume.id,
        original_filename=resume.original_filename,
        parse_status=resume.parse_status,
        parsed=parsed,
        created_at=resume.created_at,
    )


@router.get("", response_model=list[ResumeOut])
def list_resumes(session: Session = Depends(get_session)) -> list[ResumeOut]:
    rows = session.exec(select(Resume).order_by(Resume.created_at.desc())).all()
    return [_to_out(r) for r in rows]


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: str, session: Session = Depends(get_session)) -> ResumeOut:
    resume = session.get(Resume, resume_id)
    if not resume:
        raise AppError("Resume not found", status_code=404)
    return _to_out(resume)


@router.post("", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ResumeOut:
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError("Only PDF resumes are supported in MVP", status_code=400)

    profile = session.exec(select(Profile)).first()
    if not profile:
        profile = Profile(display_name="Student")
        session.add(profile)
        session.commit()
        session.refresh(profile)

    data = await file.read()
    max_bytes = settings.max_resume_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise AppError(f"Resume exceeds {settings.max_resume_mb}MB limit", status_code=400)

    resume_id = new_id()
    dest = settings.resumes_dir / f"{resume_id}.pdf"
    dest.write_bytes(data)

    resume = Resume(
        id=resume_id,
        profile_id=profile.id,
        original_filename=file.filename,
        file_path=str(dest),
        parse_status="pending",
        created_at=utcnow(),
    )
    session.add(resume)
    session.commit()

    try:
        raw_text, parsed, _meta = await parse_resume(Path(dest))
        resume.raw_text = raw_text
        resume.parsed_json = parsed.model_dump_json()
        resume.parse_status = "ok"
    except AppError as exc:
        resume.parse_status = "failed"
        resume.raw_text = str(exc.message)
        session.add(resume)
        session.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        resume.parse_status = "failed"
        resume.raw_text = str(exc)
        session.add(resume)
        session.commit()
        raise AppError(f"Resume parse failed: {exc}", status_code=500) from exc

    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_out(resume)


@router.delete("/{resume_id}")
def delete_resume(resume_id: str, session: Session = Depends(get_session)) -> dict:
    resume = session.get(Resume, resume_id)
    if not resume:
        raise AppError("Resume not found", status_code=404)
    path = Path(resume.file_path)
    if path.exists():
        path.unlink(missing_ok=True)
    session.delete(resume)
    session.commit()
    return {"ok": True}
