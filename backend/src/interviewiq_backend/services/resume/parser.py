from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pymupdf

from interviewiq_backend.api.schemas import ParsedResume
from interviewiq_backend.core.errors import AppError
from interviewiq_backend.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

PARSE_SYSTEM = """You are an expert resume parser for college students preparing for tech interviews.
Extract structured information from the resume text.
Return ONLY valid JSON matching this schema:
{
  "full_name": string,
  "email": string,
  "phone": string,
  "summary": string,
  "skills": string[],
  "projects": [{"name": string, "description": string, "tech_stack": string[], "impact": string, "highlights": string[]}],
  "education": [{"institution": string, "degree": string, "field": string, "dates": string, "gpa": string|null}],
  "experience": [{"company": string, "title": string, "dates": string, "bullets": string[]}],
  "achievements": string[],
  "inferred_seniority": "student"|"intern"|"new_grad"|"mid"
}
Be precise. Prefer empty arrays over inventing facts."""


def extract_text_from_pdf(path: Path) -> str:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Could not open PDF: {exc}", status_code=400) from exc
    parts: list[str] = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    text = "\n".join(parts).strip()
    if not text:
        raise AppError(
            "This PDF has no extractable text (it may be a scanned/image-only file). "
            "Please upload a text-based PDF exported from your resume editor.",
            status_code=400,
        )
    return text


# Longest first so "Spring Boot" wins over "Spring", "React Native" over "React".
TECH_TERMS: tuple[str, ...] = (
    "Spring Boot", "React Native", "Node.js", "FastAPI", "PostgreSQL",
    "JavaScript", "TypeScript", "Python", "MongoDB", "Redis", "Docker",
    "Kubernetes", "GraphQL", "Terraform", "TensorFlow", "PyTorch", "Pandas",
    "Scikit-learn", "OpenCV", "Kubernetes", "Firebase", "Supabase", "SQLite",
    "Elasticsearch", "RabbitMQ", "Kafka", "Airflow", "Power BI", "Tableau",
    "CI/CD", "Next.js", "Angular", "Vue.js", "Express", "Flask", "Django",
    "Spring", "AWS", "GCP", "Azure", "Linux", "GitHub", "GitLab", "Jenkins",
    "Selenium", "Pytest", "Jest", "Redux", "Svelte", "Kotlin", "Swift",
    "Go", "Rust", "Ruby", "PHP", "Java", "C++", "C#", "HTML", "CSS",
    "Tailwind", "SQL", "REST", "R", "MATLAB", "Hadoop", "Spark", "Unity",
    "Unreal", "Solidity", "Web3", "LLM", "LangChain", "Pinecone", "LanceDB",
    "RAG", "API", "Git", "C",
)

_SECTION_HEADERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("summary", ("summary", "objective", "profile", "about", "about me", "professional summary")),
    ("skills", ("skills", "technical skills", "tech stack", "techstack", "technologies",
                "tools & technologies", "languages and tools", "core competencies",
                "technical proficiency", "technical")),
    ("projects", ("projects", "selected projects", "personal projects", "academic projects",
                 "key projects", "major projects", "project experience")),
    ("experience", ("experience", "work experience", "employment history", "professional experience",
                    "work history", "relevant experience")),
    ("internships", ("internships", "internship experience", "internship")),
    ("education", ("education", "academic background", "academics", "academic qualifications",
                  "qualifications", "education details", "academic")),
    ("achievements", ("achievements", "awards", "honors", "honours", "certifications",
                      "certificates", "extracurricular activities", "activities",
                      "volunteer experience", "leadership")),
)

_PHRASE_TO_KEY: dict[str, str] = {
    phrase: key
    for key, phrases in _SECTION_HEADERS
    for phrase in phrases
}

_DATE_RANGE = re.compile(
    r"(?i)\b(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?"
    r"(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|now)\b"
)


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _find_sections(text: str) -> dict[str, list[str]]:
    """Split the resume into labeled sections by their header lines.

    Handles both bare headers ("Skills") and inline ones ("Skills: Python, React, SQL").
    """
    lines = text.splitlines()
    found: list[tuple[int, str, str]] = []
    for i, raw in enumerate(lines):
        s = _norm(raw).strip(" \t").lower().rstrip(".")
        if not s or len(s) > 90:
            continue
        for phrase, key in _PHRASE_TO_KEY.items():
            if s == phrase:
                found.append((i, key, ""))
                break
            if s.startswith(phrase):
                remainder = s[len(phrase):].lstrip()
                # Header must be followed by punctuation or a short rest, not a sentence.
                if re.match(r"^[:.\-–—|\s]", remainder) and len(remainder) <= 45:
                    # Take the tail from the ORIGINAL line to preserve casing.
                    m = re.search(re.escape(phrase), raw, re.IGNORECASE)
                    tail = _norm(raw[m.end():]).strip(" :.-\t•*|") if m else ""
                    found.append((i, key, tail))
                    break

    sections: dict[str, list[str]] = {}
    for n, (idx, key, inline) in enumerate(found):
        end = found[n + 1][0] if n + 1 < len(found) else len(lines)
        content = []
        if inline:
            content.append(inline)
        content += [_norm(lines[j]) for j in range(idx + 1, end)]
        content = [c for c in content if c]
        target = "experience" if key == "internships" else key
        sections.setdefault(target, []).extend(content)
    return sections


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*[-•*–▪◦►·]\s*", line)) or bool(
        re.match(r"^\s*\d{1,2}[.)]\s+", line)
    )


def _clean_title(s: str) -> str:
    """Drop a subtitle after '—', '|', '·', '–' (e.g. 'Campus Hub · Full-stack portal')."""
    for sep in ("—", "|", "·", "–"):
        if sep in s:
            s = s.split(sep, 1)[0]
    return _norm(s).strip(" ,;:-").strip()


def _looks_like_project_title(s: str) -> bool:
    if len(s) > 75 or not s:
        return False
    if re.search(r"[—|·–]", s):
        return True
    if re.search(r"\b(?:19|20)\d{2}\b", s):
        return True
    if re.search(r"\b(?:React|Node|Python|Java|C\+\+|Django|Flask|AWS|Docker|SQL|MongoDB|REST|API|Kotlin|Swift|Go|Rust)\b", s):
        return True
    words = s.split()
    return len(words) <= 6 and s[:1].isupper() and bool(re.fullmatch(r"[A-Za-z0-9 .&+'\-]+", s))


def _extract_tech(blob: str) -> list[str]:
    low = blob.lower()
    found: list[str] = []
    for term in TECH_TERMS:
        tl = term.lower()
        if not re.search(r"(?<![A-Za-z0-9+#])" + re.escape(tl) + r"(?![A-Za-z0-9+#])", low):
            continue
        # Prefer the longest match: skip a shorter term already covered.
        if any(f.lower().startswith(tl) or tl.startswith(f.lower()) for f in found):
            continue
        found.append(term)
    return found[:10]


def _extract_impact(description: str) -> str:
    for clause in re.split(r"[.;•\n]", description):
        c = clause.strip()
        if re.search(r"\d", c) and len(c) > 8:
            return c[:200]
    return ""


def _parse_skills(lines: list[str]) -> list[str]:
    text = " ".join(lines)
    parts = re.split(r"[,;|•·\n]+", text)
    out: list[str] = []
    for p in parts:
        s = _norm(p).strip(" -•*\t")
        if not s or len(s) > 40:
            continue
        if s.lower() in {"and", "or", "the", "of"}:
            continue
        if s not in out:
            out.append(s)
    return out[:40]


def _parse_projects(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    cur: dict | None = None
    for raw in lines:
        s = _norm(raw)
        if not s:
            continue
        if _is_bullet(raw):
            if cur is not None:
                cur["description"] = _norm(cur["description"] + " " + s)
            continue
        if cur is None or (_looks_like_project_title(s) and cur["description"]):
            name = _clean_title(s)
            if name and len(name) >= 3:
                cur = {"name": name, "description": "", "tech_stack": [], "impact": "", "highlights": []}
                items.append(cur)
            elif cur is not None:
                cur["description"] = _norm(cur["description"] + " " + s)
            continue
        if cur is not None:
            cur["description"] = _norm(cur["description"] + " " + s)

    for it in items:
        blob = it["name"] + " " + it["description"]
        it["tech_stack"] = _extract_tech(blob)
        it["impact"] = _extract_impact(it["description"])
    return items[:10]


_ACTION_VERBS = (
    "built", "created", "developed", "designed", "implemented", "worked", "improved",
    "reduced", "increased", "led", "managed", "automated", "launched", "engineered",
    "delivered", "shipped", "optimized", "refactored", "migrated", "integrated",
    "collaborated", "maintained", "tested", "deployed", "wrote", "analyzed",
    "analysed", "conducted", "assisted", "supported", "helped", "used", "made",
    "added", "set", "setup", "configured", "resolved", "identified", "performed",
)


def _role_company(parts: list[str]) -> tuple[str, str] | None:
    role, company = _norm(parts[0]), _norm(parts[1])
    if not role or not company:
        return None
    # A role/company line is short and noun-like; sentences and bullets are not.
    for part in (role, company):
        if len(part) > 60 or len(part.split()) > 6:
            return None
        if part.endswith((".", ";", "!")):
            return None
        if part.split()[0].lower() in _ACTION_VERBS:
            return None
    companyish = re.compile(r"(?i)\b(inc|llc|ltd|corp|company|technologies|solutions|labs|"
                            r"systems|group|university|college|institute|school)\b")
    if companyish.search(role) and not companyish.search(company):
        role, company = company, role
    role = _DATE_RANGE.sub("", role).strip(" ,;")
    company = _DATE_RANGE.sub("", company).strip(" ,;")
    role = _norm(role).strip(" ,;-")
    company = _norm(company).strip(" ,;-")
    if not role or not company:
        return None
    return role[:80], company[:80]


def _parse_role_line(s: str) -> tuple[str, str] | None:
    """Parse 'Role, Company' / 'Role | Company' / 'Role at Company' / 'Role - Company'."""
    if s.count("|") in (1, 2):
        parts = [p for p in s.split("|") if _norm(p)]
        if 2 <= len(parts) <= 3:
            return _role_company(parts)
    if " at " in s:
        parts = [p for p in re.split(r"(?i)\s+at\s+", s) if _norm(p)]
        if len(parts) == 2:
            return _role_company(parts)
    if s.count("@") == 1:
        parts = [p for p in s.split("@") if _norm(p)]
        if len(parts) == 2:
            return _role_company(parts)
    if re.search(r"\s[—–]\s", s):
        parts = [p for p in re.split(r"\s[—–]\s", s) if _norm(p)]
        if 2 <= len(parts) <= 3:
            return _role_company(parts)
    parts = [p for p in s.split(",") if _norm(p)]
    if len(parts) == 2:
        return _role_company(parts)
    return None


def _parse_experience(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    cur: dict | None = None
    for raw in lines:
        s = _norm(raw)
        if not s:
            continue
        if _is_bullet(raw):
            if cur is not None:
                cur["bullets"].append(s)
            continue
        parsed = _parse_role_line(s)
        if parsed:
            if cur is not None:
                entries.append(cur)
            role, company = parsed
            dates = _DATE_RANGE.search(raw)
            cur = {
                "company": company,
                "title": role,
                "dates": _norm(dates.group(0)) if dates else "",
                "bullets": [],
            }
        elif cur is not None:
            cur["bullets"].append(s)
    if cur is not None:
        entries.append(cur)
    return entries[:8]


_DEGREE_RE = re.compile(
    r"(?i)\b(B\.?\s?Tech|B\.?\s?E\.?|BSc|B\.?\s?S\.?|M\.?\s?Tech|M\.?\s?S\.?|MBA|"
    r"M\.?\s?Eng|Ph\.?\s?D|Bachelor(?:\s+of\s+[A-Za-z ]+)?|Master(?:\s+of\s+[A-Za-z ]+)?|"
    r"B\.?\s?A\.?|M\.?\s?A\.?|Diploma|Higher Secondary|CBSE|ICSE)\b"
)


def _parse_education(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    for raw in lines:
        s = _norm(raw)
        if not s:
            continue
        deg = _DEGREE_RE.search(s)
        gpa = re.search(r"(?i)(?:GPA|CGPA)\s*[:=]?\s*([0-4]\.\d+)", s)
        field = ""
        institution = s
        if deg:
            after = _norm(s[deg.end():]).strip(" ,;-–—|")
            field = after.split(",")[0].strip()[:80] if after else ""
            rest = [p.strip() for p in s.split(",")[1:] if p.strip()]
            if rest:
                institution = _DATE_RANGE.sub("", rest[0]).strip(" ,;-")
        institution = _norm(institution)
        dates = _DATE_RANGE.search(s)
        items.append({
            "institution": institution[:120],
            "degree": (deg.group(0) if deg else s[:60])[:120],
            "field": field,
            "dates": _norm(dates.group(0)) if dates else "",
            "gpa": gpa.group(1) if gpa else None,
        })
    return items[:5]


def _heuristic_parse(raw_text: str) -> ParsedResume:
    """Offline fallback when no API key is available.

    Sections are located by their header lines, then each section is parsed
    into structured resume data (skills, projects, experience, education).
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
    phone_match = re.search(r"(\+?\d[\d\s\-()]{8,}\d)", raw_text)

    sections = _find_sections(raw_text)
    skills = _parse_skills(sections.get("skills", []))
    projects = _parse_projects(sections.get("projects", []))
    experience = _parse_experience(sections.get("experience", []))
    education = _parse_education(sections.get("education", []))
    achievements = [s for s in sections.get("achievements", []) if not _is_bullet(s)][:10]
    summary = " ".join(sections.get("summary", []))[:500]

    if not summary and len(lines) > 1:
        summary = _norm(lines[1])[:500]

    return ParsedResume(
        full_name=_clean_title(lines[0]) if lines else "",
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0) if phone_match else "",
        summary=summary,
        skills=skills,
        projects=projects,  # type: ignore[arg-type]
        education=education,  # type: ignore[arg-type]
        experience=experience,  # type: ignore[arg-type]
        achievements=achievements,
        inferred_seniority="student",
    )


async def parse_resume(path: Path, raw_text: str | None = None) -> tuple[str, ParsedResume, dict]:
    text = raw_text or extract_text_from_pdf(path)
    client = OpenRouterClient()
    if not client.api_key:
        parsed = _heuristic_parse(text)
        return text, parsed, {"model": "heuristic", "usage": {}}

    truncated = text[:14000]
    messages = [
        {"role": "system", "content": PARSE_SYSTEM},
        {"role": "user", "content": truncated},
    ]
    try:
        data, meta = await client.chat_json(messages, temperature=0.1)
        parsed = ParsedResume.model_validate(data)
        return text, parsed, meta
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM resume parse failed, using heuristic: %s", exc)
        parsed = _heuristic_parse(text)
        return text, parsed, {"model": "heuristic-fallback", "usage": {}, "error": str(exc)}


def resume_summary_for_prompt(parsed: ParsedResume) -> str:
    return json.dumps(parsed.model_dump(), indent=2)
