from __future__ import annotations

import re
from pathlib import Path

from .extensions import db
from .models import ApplicantDetail, Application, Resume, User
from .resume_parser import extract_resume_text, normalize_resume_text

SKILL_TERMS = [
    "python", "java", "javascript", "typescript", "react", "next.js", "node.js", "express", "flask", "django",
    "fastapi", "sql", "postgresql", "mysql", "sqlite", "mongodb", "redis", "aws", "azure", "gcp", "docker",
    "kubernetes", "git", "linux", "html", "css", "tailwind", "figma", "ui/ux", "machine learning", "deep learning",
    "nlp", "computer vision", "llm", "langchain", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "data analysis", "rest api", "graphql", "mern", "full stack", "backend", "frontend", "devops", "ci/cd",
]

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:(?:\+?91[\s-]?)|0)?[6-9]\d{2}[\s-]?\d{3}[\s-]?\d{4}")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[A-Z0-9.-]+\.[A-Z]{2,}(?:/[\w./?%&=+#:-]*)?", re.I)
EXPERIENCE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)
NOTICE_RE = re.compile(r"notice\s*period\s*[:\-]?\s*([^\n|,;]{2,80})", re.I)
ROLE_KEYWORDS_RE = re.compile(r"\b(?:developer|engineer|intern|designer|analyst|manager|architect|consultant|trainee|specialist|lead|full[ -]?stack|frontend|backend|ai/ml|machine learning|data scientist)\b", re.I)

PRIORITY_LOCATION_ALIASES = {
    "Greater Noida": ["greater noida", "gr noida"],
    "New Delhi": ["new delhi"],
    "Delhi": ["delhi"],
    "Noida": ["noida"],
    "Ghaziabad": ["ghaziabad"],
    "Gurugram": ["gurugram", "gurgaon"],
    "Faridabad": ["faridabad"],
    "NCR": ["ncr", "delhi ncr", "delhi-ncr"],
}
KNOWN_LOCATION_NAMES = [
    "Bengaluru", "Bangalore", "Mumbai", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Jaipur",
    "Lucknow", "Kanpur", "Indore", "Bhopal", "Raipur", "Bhilai", "Durg", "Bilaspur", "Nagpur", "Chandigarh",
    "Mohali", "Dehradun", "Patna", "Ranchi", "Bhubaneswar", "Kochi", "Coimbatore", "Surat", "Vadodara",
    "Chhattisgarh", "Uttar Pradesh", "Haryana", "Rajasthan", "Madhya Pradesh", "Maharashtra", "Karnataka",
]
MEDIUM_LOCATION_NAMES = {"Uttar Pradesh", "Haryana", "Rajasthan", "Chandigarh", "Mohali"}


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def _find_urls(text: str) -> list[str]:
    values = []
    for match in URL_RE.findall(text):
        cleaned = match.rstrip(".,);]")
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values[:30]


def _find_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in SKILL_TERMS:
        token = skill.lower()
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", lowered):
            found.append(skill)
    return found


def _section_excerpt(text: str, heading: str, max_chars: int = 1600) -> str | None:
    pattern = re.compile(rf"(?:^|\n)\s*{re.escape(heading)}\s*[:\-]?\s*\n?(.*?)(?=\n\s*[A-Z][A-Z /&-]{{3,}}\s*\n|\Z)", re.I | re.S)
    match = pattern.search(text)
    if not match:
        return None
    return normalize_resume_text(match.group(1))[:max_chars] or None

def _contains_location(text: str, value: str) -> bool:
    pattern = re.escape(value.lower()).replace("\\ ", r"[\s\-]+")
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()))


def detect_resume_location(text: str) -> str | None:
    if not text:
        return None
    for canonical, aliases in PRIORITY_LOCATION_ALIASES.items():
        for alias in aliases:
            if _contains_location(text, alias):
                return canonical
    for location in KNOWN_LOCATION_NAMES:
        if _contains_location(text, location):
            return location
    location_line = re.search(r"(?:location|address|current\s+city)\s*[:\-]\s*([^\n]{2,120})", text, re.I)
    if location_line:
        cleaned = normalize_resume_text(location_line.group(1))[:120]
        return cleaned or None
    return None


def resume_location_priority(location: str | None) -> str:
    if not location:
        return "Unknown"
    if any(location == canonical for canonical in PRIORITY_LOCATION_ALIASES):
        return "High"
    if location in MEDIUM_LOCATION_NAMES:
        return "Medium"
    return "Low"


def _find_current_role(text: str) -> str | None:
    for raw_line in text.splitlines()[:45]:
        line = normalize_resume_text(raw_line).strip(" -|\t")
        if not line or len(line) > 120:
            continue
        lowered = line.lower()
        if "@" in line or "http" in lowered or lowered.startswith(("email", "phone", "mobile", "address", "skills")):
            continue
        if ROLE_KEYWORDS_RE.search(line):
            return line[:120]
    return None


def _find_notice_period(text: str) -> str | None:
    match = NOTICE_RE.search(text or "")
    return normalize_resume_text(match.group(1))[:80] if match else None


def parse_resume_fields(text: str, candidate: User, email_info: dict | None = None) -> dict:
    urls = _find_urls(text)
    linkedin = next((url for url in urls if "linkedin.com" in url.lower()), None)
    github = next((url for url in urls if "github.com" in url.lower()), None)
    portfolio = next((url for url in urls if url not in {linkedin, github}), None)
    emails = []
    for value in EMAIL_RE.findall(text):
        if value.lower() not in [item.lower() for item in emails]:
            emails.append(value)
    phones = []
    for value in PHONE_RE.findall(text):
        cleaned = re.sub(r"\s+", " ", value).strip()
        if cleaned not in phones:
            phones.append(cleaned)
    experience_values = [float(match.group(1)) for match in EXPERIENCE_RE.finditer(text)]
    detected_location = detect_resume_location(text)
    current_role = _find_current_role(text)
    notice_period = _find_notice_period(text)
    profile = candidate.profile
    return {
        "emails": emails[:10],
        "phones": phones[:10],
        "urls": urls,
        "linkedin_url": linkedin or (profile.linkedin_url if profile else None),
        "github_url": github or (profile.github_url if profile else None),
        "portfolio_url": portfolio or (profile.portfolio_url if profile else None),
        "skills": _find_skills(text),
        "experience_years_detected": max(experience_values) if experience_values else None,
        "detected_location": detected_location,
        "location_priority": resume_location_priority(detected_location),
        "current_role_detected": current_role,
        "notice_period_detected": notice_period,
        "summary_excerpt": normalize_resume_text(text)[:1200],
        "education_excerpt": _section_excerpt(text, "education"),
        "experience_excerpt": _section_excerpt(text, "experience") or _section_excerpt(text, "work experience"),
        "projects_excerpt": _section_excerpt(text, "projects"),
        "certifications_excerpt": _section_excerpt(text, "certifications"),
        "email_subject": (email_info or {}).get("subject"),
    }


def create_or_update_applicant_detail(application: Application) -> ApplicantDetail:
    candidate = application.candidate
    resume: Resume | None = application.resume
    answers = application.answers or {}
    email_info = answers.get("email") if isinstance(answers, dict) and isinstance(answers.get("email"), dict) else {}
    detail = ApplicantDetail.query.filter_by(application_id=application.id).first() or ApplicantDetail(application_id=application.id)

    resume_text = ""
    status = "missing_resume"
    error = None
    if resume:
        path = Path(resume.storage_path)
        if path.exists():
            raw = path.read_bytes()
            resume_text, status, error = extract_resume_text(resume.original_filename, raw, resume.content_type)
        else:
            status = "missing_file"
            error = "Stored resume file was not found on disk."

    parsed = parse_resume_fields(resume_text, candidate, email_info) if resume_text else {}
    profile = candidate.profile
    detail.candidate_id = application.candidate_id
    detail.resume_id = application.resume_id
    detail.source = application.source
    detail.full_name = candidate.full_name
    detail.email = candidate.email
    detail.phone = (parsed.get("phones") or [None])[0] or (profile.phone if profile else None)
    detail.current_city = parsed.get("detected_location") or (profile.current_city if profile else None)
    detail.current_role = parsed.get("current_role_detected") or (profile.current_role if profile else None)
    detail.linkedin_url = parsed.get("linkedin_url")
    detail.github_url = parsed.get("github_url")
    detail.portfolio_url = parsed.get("portfolio_url")
    detail.email_subject = email_info.get("subject")
    detail.email_message_id = email_info.get("message_id")
    detail.email_sent_at = email_info.get("sent_at")
    detail.resume_filename = resume.original_filename if resume else None
    detail.resume_content_type = resume.content_type if resume else None
    detail.resume_size_bytes = resume.size_bytes if resume else None
    detail.resume_text = resume_text
    detail.parsed_fields = parsed
    detail.extraction_status = status
    detail.extraction_error = error
    db.session.add(detail)
    db.session.flush()
    return detail


def rebuild_applicant_details(limit: int | None = None) -> dict:
    query = Application.query.filter(Application.resume_id.isnot(None)).order_by(Application.created_at.desc())
    if limit:
        query = query.limit(limit)
    created_or_updated = 0
    failed = 0
    errors: list[dict[str, str]] = []
    application_ids = [application.id for application in query.all()]
    for application_id in application_ids:
        try:
            application = Application.query.get(application_id)
            if not application:
                continue
            create_or_update_applicant_detail(application)
            db.session.commit()
            created_or_updated += 1
        except Exception as exc:
            db.session.rollback()
            failed += 1
            errors.append({"application_id": application_id, "error": str(exc)[:300]})
    return {"created_or_updated": created_or_updated, "failed": failed, "errors": errors[:20]}