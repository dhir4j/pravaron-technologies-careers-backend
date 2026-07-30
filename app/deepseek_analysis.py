from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import timezone
from typing import Any

from flask import current_app

from .applicant_details import create_or_update_applicant_detail, resume_location_priority
from .extensions import db
from .models import Application, CandidateAnalysis, InconsistencyFlag, utcnow


ANALYSIS_SCHEMA_HINT = {
    "suitability_score": "integer 0-100",
    "confidence_score": "integer 0-100",
    "recommendation": "Strong fit | Good fit | Possible fit | Weak fit | Reject",
    "graduation_year": "integer graduation year if found, else null",
    "recommended_track": "Internship | Full-time | Unclear",
    "location_priority": "High | Medium | Low | Unknown",
    "detected_location": "candidate location if found",
    "job_family": "ai_ml_backend | ai_ml | full_stack | frontend | ui_ux | other",
    "headline": "one concise sentence",
    "summary": "short hiring summary",
    "experience_summary": "work experience summary",
    "education_summary": "education summary",
    "projects_summary": "project summary",
    "skills": ["skill"],
    "languages": ["programming/spoken language"],
    "frameworks": ["framework/library"],
    "tools": ["tool/platform/database"],
    "strengths": ["strength"],
    "concerns": ["concern or gap"],
    "project_highlights": [{"name": "project name", "description": "what they built", "technologies": ["tech"]}],
    "job_fit": {
        "matched_requirements": ["matched job requirement"],
        "missing_or_unclear_requirements": ["gap"],
        "fit_reasoning": "brief explanation",
    },
    "interview_questions": ["question"],
}


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean_resume_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.72)]
    tail = text[-int(max_chars * 0.28) :]
    return f"{head}\n\n[...resume truncated to reduce API usage...]\n\n{tail}"


def _analysis_input(application: Application, max_resume_chars: int) -> dict:
    detail = create_or_update_applicant_detail(application)
    candidate = application.candidate
    job = application.job
    profile = candidate.profile
    parsed_fields = detail.parsed_fields or {}
    return {
        "candidate": {
            "name": candidate.full_name,
            "email": candidate.email,
            "phone": detail.phone or (profile.phone if profile else None),
            "profile": {
                "current_city": detail.current_city,
                "current_role": detail.current_role,
                "total_experience_years": parsed_fields.get("experience_years_detected") or (profile.total_experience_years if profile else None),
                "skills": profile.skills if profile else [],
                "linkedin_url": detail.linkedin_url or (profile.linkedin_url if profile else None),
                "github_url": detail.github_url or (profile.github_url if profile else None),
                "portfolio_url": detail.portfolio_url or (profile.portfolio_url if profile else None),
            },
        },
        "application": {
            "id": application.id,
            "source": application.source,
            "email_subject": detail.email_subject,
            "email_sent_at": detail.email_sent_at,
            "cover_message": (application.cover_message or "")[:3000],
        },
        "job": {
            "title": job.title,
            "department": job.department,
            "employment_type": job.employment_type,
            "experience_level": job.experience_level,
            "location": job.location,
            "role_summary": job.role_summary,
            "responsibilities": job.responsibilities,
            "required_skills": job.required_skills or [],
            "preferred_skills": job.preferred_skills or [],
            "experience_requirement": job.experience_requirement,
            "education_preference": job.education_preference,
            "role_family": (job.source_metadata or {}).get("role_family"),
            "target_track": (job.source_metadata or {}).get("target_track"),
            "priority_locations": (job.source_metadata or {}).get("priority_locations") or ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"],
        },
        "resume": {
            "filename": detail.resume_filename,
            "content_type": detail.resume_content_type,
            "size_bytes": detail.resume_size_bytes,
            "parsed_fields_before_llm": parsed_fields,
            "detected_location_from_resume_only": parsed_fields.get("detected_location"),
            "location_priority_from_resume_only": parsed_fields.get("location_priority"),
            "text": _clean_resume_text(detail.resume_text or "", max_resume_chars),
        },
    }


def _hash_input(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _year_int(value) -> int | None:
    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None
    return year if 1990 <= year <= 2035 else None


def _bounded_int(value, default: int | None = None) -> int | None:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, number))


def _as_list(value) -> list:
    if isinstance(value, list):
        return value[:20]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _extract_json(content: str) -> dict:
    content = (content or "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


DEEPSEEK_ANALYSIS_SYSTEM_INSTRUCTIONS = """
You are a senior technical recruiter preparing an evidence-based candidate analysis for Pravaron Technologies.

Use only the provided JSON payload. The payload contains candidate details, parsed resume fields, the full extracted resume text, and the exact applied job/JD. Do not use outside knowledge, assumptions, or generic praise.

Primary objective:
- Extract structured, useful hiring information from the resume.
- Compare the candidate against the exact applied job description, not against a generic role.
- Produce concise evidence that helps a human recruiter decide what to review next.

Hard rules:
- Return one valid compact JSON object only, matching the requested shape.
- Do not invent facts. If evidence is missing, use null, empty arrays, or list the item under missing_or_unclear_requirements.
- For detected_location and location_priority, use only location evidence found in resume.text or resume.parsed_fields_before_llm. Never use the email message, company office, job location, or priority_locations to infer candidate location.
- Do not let location alone make a candidate a strong fit. Location is only a small preference when role evidence is otherwise similar.
- Do not over-score or over-recommend candidates with weak JD evidence. A strong recommendation requires clear resume evidence for several required skills plus relevant projects or experience.
- Treat 2025/2026 graduates as internship-aligned and 2023/2024 or earlier graduates as full-time-aligned unless the resume clearly says otherwise.
- Keep summaries specific. Mention technologies, projects, experience, and gaps only when they are present in the resume.

Report guidance:
- summary: 2-4 sentences focused on role fit.
- experience_summary, projects_summary, education_summary: extract the most relevant facts, not a biography.
- skills/languages/frameworks/tools: include only items supported by the resume text.
- job_fit.matched_requirements: list JD requirements with resume evidence.
- job_fit.missing_or_unclear_requirements: list important JD requirements not clearly supported by the resume.
- concerns: include gaps, unclear evidence, missing links, weak project proof, track mismatch, or location mismatch where relevant.
- interview_questions: ask practical questions that verify unclear or important claims.

The backend calculates the final stored suitability score using deterministic JD/resume matching. Your suitability_score is only an advisory estimate and must not be inflated.
""".strip()

def _call_deepseek(payload: dict) -> tuple[dict, dict]:
    api_key = current_app.config["DEEPSEEK_API_KEY"]
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")
    body = {
        "model": current_app.config["DEEPSEEK_MODEL"],
        "messages": [
            {
                "role": "system",
                "content": DEEPSEEK_ANALYSIS_SYSTEM_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Extract useful candidate details and evaluate fit for the job.",
                        "required_json_shape": ANALYSIS_SCHEMA_HINT,
                        "data": payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 1400,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{current_app.config['DEEPSEEK_API_BASE_URL']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=current_app.config["DEEPSEEK_ANALYSIS_TIMEOUT_SECONDS"]) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {exc.code}: {error_body[:500]}") from exc
    content = response_data["choices"][0]["message"].get("content") or "{}"
    return _extract_json(content), response_data.get("usage") or {}


def _matchable_text(*values) -> str:
    chunks: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            chunks.append(_matchable_text(*value.values()))
        elif isinstance(value, list):
            chunks.append(_matchable_text(*value))
        else:
            chunks.append(str(value))
    text = " ".join(chunks).lower()
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    collapsed = re.sub(r"\s+", " ", text).strip()
    return f" {collapsed} "


def _term_variants(term: str) -> list[str]:
    base = str(term or "").strip().lower()
    if not base:
        return []
    variants = {base}
    variants.add(base.replace("/", " ").replace(".", " ").replace("-", " "))
    variants.add(re.sub(r"\b(?:basics?|fundamentals?|knowledge|development|design|responsive|clear)\b", "", base).strip())
    aliases = {
        "next.js": ["next js", "nextjs"],
        "rest apis": ["rest api", "rest", "api"],
        "rest api": ["rest apis", "api"],
        "postgresql": ["postgres", "psql"],
        "mongodb": ["mongo db", "mongo"],
        "machine learning basics": ["machine learning", "ml"],
        "generative ai": ["gen ai", "genai", "large language model", "llm"],
        "llm basics": ["llm", "large language model"],
        "tailwind css": ["tailwind"],
        "ui design": ["ui"],
        "ux design": ["ux"],
        "information architecture": ["ia"],
        "responsive web development": ["responsive"],
    }
    variants.update(aliases.get(base, []))
    normalized: list[str] = []
    for variant in variants:
        clean = _matchable_text(variant).strip()
        if clean and clean not in normalized:
            normalized.append(clean)
            if clean.endswith("s"):
                normalized.append(clean[:-1])
    return normalized


def _term_matches(term: str, evidence_text: str) -> bool:
    return any(f" {variant} " in evidence_text for variant in _term_variants(term))


def _matched_terms(terms: list[str], evidence_text: str) -> list[str]:
    return [term for term in terms if _term_matches(term, evidence_text)]


def _experience_requirement_bounds(value: str | None) -> tuple[float | None, float | None]:
    text = str(value or "").lower()
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“]\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", text)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    max_match = re.search(r"0\s*[-ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“]\s*(\d+(?:\.\d+)?)", text)
    if max_match:
        return 0.0, float(max_match.group(1))
    single = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", text)
    if single:
        value_num = float(single.group(1))
        return max(0.0, value_num - 0.5), value_num + 1.5
    return None, None


def _track_score(job, raw: dict, parsed_fields: dict, experience_years: float | None) -> tuple[int, list[str]]:
    reasons: list[str] = []
    target_track = str((job.source_metadata or {}).get("target_track") or job.employment_type or "").lower()
    graduation_year = _year_int(raw.get("graduation_year"))
    min_years, max_years = _experience_requirement_bounds(job.experience_requirement or job.experience_level)
    score = 0
    if "intern" in target_track:
        if graduation_year in {2025, 2026}:
            score += 8
            reasons.append("recent graduate aligned with internship")
        if experience_years is None or experience_years <= 1.5:
            score += 7
            reasons.append("experience level fits internship")
        elif experience_years <= 2.5:
            score += 4
            reasons.append("experience is slightly above internship range")
    else:
        if experience_years is not None and min_years is not None and max_years is not None:
            if min_years <= experience_years <= max_years + 1:
                score += 11
                reasons.append("experience fits role requirement")
            elif experience_years > 0:
                score += 6
                reasons.append("some relevant experience found")
        elif experience_years is not None and experience_years > 0:
            score += 8
            reasons.append("experience evidence found")
        if graduation_year and graduation_year <= 2024:
            score += 4
            reasons.append("graduation year aligns better with full-time track")
    return min(15, score), reasons


def _deterministic_candidate_score(application: Application, detail, raw: dict) -> dict:
    job = application.job
    parsed_fields = detail.parsed_fields or {}
    required = [str(item) for item in (job.required_skills or []) if str(item).strip()]
    preferred = [str(item) for item in (job.preferred_skills or []) if str(item).strip()]
    evidence = _matchable_text(
        detail.resume_text,
        parsed_fields,
        raw.get("skills"),
        raw.get("languages"),
        raw.get("frameworks"),
        raw.get("tools"),
        raw.get("projects_summary"),
        raw.get("experience_summary"),
        raw.get("education_summary"),
        raw.get("project_highlights"),
    )

    required_matches = _matched_terms(required, evidence)
    preferred_matches = _matched_terms(preferred, evidence)
    required_score = round(40 * len(required_matches) / len(required)) if required else 20
    preferred_score = round(15 * len(preferred_matches) / len(preferred)) if preferred else 8

    project_text = _matchable_text(parsed_fields.get("projects_excerpt"), raw.get("projects_summary"), raw.get("project_highlights"), detail.resume_text)
    has_project_section = bool(parsed_fields.get("projects_excerpt") or raw.get("projects_summary") or raw.get("project_highlights"))
    project_skill_hits = len(_matched_terms(required_matches + preferred_matches, project_text))
    project_score = 0
    if has_project_section:
        project_score += 8
    if project_skill_hits:
        project_score += min(7, project_skill_hits * 2)
    project_score = min(15, project_score)

    experience_years = parsed_fields.get("experience_years_detected")
    try:
        experience_years = float(experience_years) if experience_years is not None else None
    except (TypeError, ValueError):
        experience_years = None
    experience_score, experience_reasons = _track_score(job, raw, parsed_fields, experience_years)

    education_text = _matchable_text(parsed_fields.get("education_excerpt"), raw.get("education_summary"), detail.resume_text)
    education_terms = ["b tech", "be", "b e", "mca", "m tech", "computer science", "information technology", "ai ml", "artificial intelligence", "software engineering"]
    education_score = 5 if any(f" {term} " in education_text for term in education_terms) else (2 if education_text.strip() else 0)

    location_priority = resume_location_priority((parsed_fields or {}).get("detected_location"))
    location_score = {"High": 5, "Medium": 3, "Low": 0, "Unknown": 1}.get(location_priority, 0)

    score = max(0, min(100, required_score + preferred_score + project_score + experience_score + education_score + location_score))
    missing_required = [term for term in required if term not in required_matches]
    recommendation = "Reject"
    if score >= 78:
        recommendation = "Strong fit"
    elif score >= 65:
        recommendation = "Good fit"
    elif score >= 48:
        recommendation = "Possible fit"
    elif score >= 32:
        recommendation = "Weak fit"

    confidence = 55
    if len(detail.resume_text or "") >= 800:
        confidence += 15
    if required:
        confidence += 10
    if has_project_section:
        confidence += 10
    if raw.get("summary") or raw.get("job_fit"):
        confidence += 5

    return {
        "score": score,
        "recommendation": recommendation,
        "confidence_score": max(0, min(100, confidence)),
        "matched_required": required_matches,
        "missing_required": missing_required,
        "matched_preferred": preferred_matches,
        "location_priority": location_priority,
        "breakdown": {
            "required_skills": {"score": required_score, "max": 40, "matched": required_matches, "missing": missing_required},
            "preferred_skills": {"score": preferred_score, "max": 15, "matched": preferred_matches},
            "projects": {"score": project_score, "max": 15, "has_project_section": has_project_section},
            "experience_track": {"score": experience_score, "max": 15, "reasons": experience_reasons, "years_detected": experience_years},
            "education": {"score": education_score, "max": 5},
            "location": {"score": location_score, "max": 5, "priority": location_priority, "detected_location": parsed_fields.get("detected_location")},
        },
    }

def _store_analysis(application: Application, detail, input_hash: str, raw: dict, usage: dict, model: str) -> CandidateAnalysis:
    analysis = CandidateAnalysis.query.filter_by(application_id=application.id).first() or CandidateAnalysis(application_id=application.id)
    analysis.applicant_detail_id = detail.id
    analysis.candidate_id = application.candidate_id
    analysis.resume_id = application.resume_id
    analysis.job_id = application.job_id
    analysis.model = model
    analysis.input_hash = input_hash
    analysis.status = "completed"
    score_result = _deterministic_candidate_score(application, detail, raw)
    analysis.suitability_score = score_result["score"]
    analysis.confidence_score = score_result["confidence_score"]
    analysis.recommendation = score_result["recommendation"]
    analysis.graduation_year = _year_int(raw.get("graduation_year"))
    analysis.recommended_track = str(raw.get("recommended_track") or "").strip()[:80] or None
    resume_location = (detail.parsed_fields or {}).get("detected_location")
    analysis.location_priority = resume_location_priority(resume_location)
    analysis.detected_location = str(resume_location or "").strip()[:160] or None
    analysis.job_family = str(raw.get("job_family") or "").strip()[:120] or None
    analysis.headline = str(raw.get("headline") or "").strip()[:255] or None
    analysis.summary = str(raw.get("summary") or "").strip()[:4000]
    analysis.experience_summary = str(raw.get("experience_summary") or "").strip()[:4000]
    analysis.education_summary = str(raw.get("education_summary") or "").strip()[:3000]
    analysis.projects_summary = str(raw.get("projects_summary") or "").strip()[:4000]
    analysis.skills = _as_list(raw.get("skills"))
    analysis.languages = _as_list(raw.get("languages"))
    analysis.frameworks = _as_list(raw.get("frameworks"))
    analysis.tools = _as_list(raw.get("tools"))
    analysis.strengths = _as_list(raw.get("strengths"))
    analysis.concerns = _as_list(raw.get("concerns"))
    analysis.project_highlights = _as_list(raw.get("project_highlights"))
    job_fit = raw.get("job_fit") if isinstance(raw.get("job_fit"), dict) else {}
    job_fit["matched_requirements"] = score_result["matched_required"] or _as_list(job_fit.get("matched_requirements"))
    job_fit["missing_or_unclear_requirements"] = score_result["missing_required"] or _as_list(job_fit.get("missing_or_unclear_requirements"))
    job_fit["score_breakdown"] = score_result["breakdown"]
    job_fit["ai_suggested_suitability_score"] = _bounded_int(raw.get("suitability_score"))
    analysis.job_fit = job_fit
    analysis.interview_questions = _as_list(raw.get("interview_questions"))
    raw["backend_score"] = score_result
    analysis.raw_analysis = raw
    analysis.usage = usage
    analysis.error = None
    analysis.analyzed_at = utcnow()
    db.session.add(analysis)
    db.session.flush()
    return analysis


def analyze_application(application: Application, force: bool = False) -> tuple[CandidateAnalysis, bool]:
    if not application.resume_id:
        raise ValueError("Application does not have a resume")
    detail = create_or_update_applicant_detail(application)
    if not detail.resume_text:
        raise ValueError("Resume text is missing for this application")
    payload = _analysis_input(application, current_app.config["DEEPSEEK_ANALYSIS_MAX_RESUME_CHARS"])
    input_hash = _hash_input(payload)
    existing = CandidateAnalysis.query.filter_by(application_id=application.id).first()
    model = current_app.config["DEEPSEEK_MODEL"]
    if existing and existing.status == "completed" and existing.input_hash == input_hash and existing.model == model and not force:
        return existing, False
    try:
        raw, usage = _call_deepseek(payload)
        return _store_analysis(application, detail, input_hash, raw, usage, model), True
    except Exception as exc:
        analysis = existing or CandidateAnalysis(application_id=application.id)
        analysis.applicant_detail_id = detail.id
        analysis.candidate_id = application.candidate_id
        analysis.resume_id = application.resume_id
        analysis.job_id = application.job_id
        analysis.model = model
        analysis.input_hash = input_hash
        analysis.status = "failed"
        analysis.error = str(exc)[:2000]
        analysis.analyzed_at = utcnow()
        db.session.add(analysis)
        db.session.flush()
        raise


def detect_inconsistencies(application: Application) -> InconsistencyFlag:
    """Compare extracted resume data vs application answers and flag mismatches via DeepSeek."""
    detail = application.applicant_detail
    if not detail:
        raise ValueError("No applicant detail found for this application")

    candidate_data = {
        "name_on_resume": detail.full_name,
        "email_on_resume": detail.email,
        "phone_on_resume": detail.phone,
        "location_on_resume": detail.current_city,
        "role_on_resume": detail.current_role,
        "parsed_fields": detail.parsed_fields or {},
    }
    application_data = {
        "name_in_account": application.candidate.full_name if application.candidate else None,
        "email_in_account": application.candidate.email if application.candidate else None,
        "answers": application.answers or {},
        "cover_message_excerpt": (application.cover_message or "")[:500],
    }
    analysis_data = {}
    if application.candidate_analysis:
        a = application.candidate_analysis
        analysis_data = {
            "detected_location": a.detected_location,
            "graduation_year": a.graduation_year,
            "experience_years_from_resume": None,
        }

    schema = {
        "flags": [
            {
                "field": "field name (e.g. name, email, experience_years, location)",
                "expected": "what the resume/analysis shows",
                "found": "what the application/account shows",
                "severity": "low | medium | high",
                "explanation": "brief explanation",
            }
        ],
        "inconsistency_count": "integer",
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a recruitment data quality checker. Compare the resume-extracted data vs the candidate's application data. "
                "Flag any material inconsistencies or suspicious mismatches (e.g. different names, implausible experience, location mismatch). "
                "Minor formatting differences are NOT inconsistencies. Only flag factually contradictory information. "
                "If no inconsistencies, return {\"flags\": [], \"inconsistency_count\": 0}. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "required_json_shape": schema,
                    "resume_data": candidate_data,
                    "application_data": application_data,
                    "ai_analysis_data": analysis_data,
                },
                ensure_ascii=False,
            ),
        },
    ]

    model = current_app.config["DEEPSEEK_MODEL"]
    body = {
        "model": model,
        "messages": messages,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 600,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{current_app.config['DEEPSEEK_API_BASE_URL']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {current_app.config['DEEPSEEK_API_KEY']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=current_app.config["DEEPSEEK_ANALYSIS_TIMEOUT_SECONDS"]) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {exc.code}: {error_body[:300]}") from exc

    content = response_data["choices"][0]["message"].get("content") or "{}"
    raw = _extract_json(content)
    flags = raw.get("flags") if isinstance(raw.get("flags"), list) else []

    existing = InconsistencyFlag.query.filter_by(application_id=application.id).first()
    flag_record = existing or InconsistencyFlag(application_id=application.id)
    flag_record.flags = flags[:20]
    flag_record.reviewed = False
    db.session.add(flag_record)
    db.session.commit()
    return flag_record


def analyze_applications(limit: int | None = None, force: bool = False) -> dict:
    query = Application.query.filter(Application.source == "email", Application.resume_id.isnot(None)).order_by(Application.created_at.desc())
    if limit:
        query = query.limit(limit)
    summary = {"checked": 0, "analyzed": 0, "cached": 0, "failed": 0, "errors": [], "analysis_ids": []}
    for application in query.all():
        summary["checked"] += 1
        try:
            analysis, created = analyze_application(application, force=force)
            db.session.commit()
            if created:
                summary["analyzed"] += 1
            else:
                summary["cached"] += 1
            summary["analysis_ids"].append(analysis.id)
        except Exception as exc:
            db.session.rollback()
            summary["failed"] += 1
            summary["errors"].append({"application_id": application.id, "error": str(exc)[:500]})
    return summary