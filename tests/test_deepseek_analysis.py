from __future__ import annotations

from types import SimpleNamespace

from app import create_app
from app.deepseek_analysis import _deterministic_candidate_score, _post_deepseek, _normalized_job_requirements, _validate_candidate_analysis


def _job():
    return SimpleNamespace(
        title="Full-Stack Software Developer",
        employment_type="Full-time",
        experience_level="Early Career",
        experience_requirement="1-2 years relevant full-stack or software-development experience.",
        required_skills=[
            "JavaScript", "TypeScript", "React", "Next.js", "HTML", "CSS", "Tailwind CSS", "Python", "Flask",
            "REST APIs", "PostgreSQL", "SQL", "MongoDB", "Authentication", "Git", "Testing", "Linux", "Deployment",
        ],
        preferred_skills=["Node.js", "Docker", "Redis", "AWS", "CI/CD", "LLM APIs"],
        education_preference="B.Tech Computer Science or related field.",
        workplace_model="On-site",
        location="Noida",
        source_metadata={"target_track": "Full-time"},
    )


def test_deterministic_score_uses_resume_evidence_against_applied_jd():
    application = SimpleNamespace(job=_job())
    strong_detail = SimpleNamespace(
        resume_text=(
            "B.Tech Computer Science 2023. Full Stack Developer with 1.5 years experience. "
            "Projects: built React Next.js TypeScript Tailwind dashboard with Flask REST APIs, PostgreSQL, MongoDB, "
            "authentication, Git, Linux deployment and tests. Docker and AWS exposure. Location: Bhilai."
        ),
        parsed_fields={
            "detected_location": "Bhilai",
            "experience_years_detected": 1.5,
            "projects_excerpt": "React Next.js TypeScript dashboard, Flask REST APIs, PostgreSQL, MongoDB authentication.",
            "education_excerpt": "B.Tech Computer Science 2023",
        },
    )
    weak_detail = SimpleNamespace(
        resume_text="UI portfolio. Figma wireframes and brand posters. Location: Noida.",
        parsed_fields={"detected_location": "Noida", "projects_excerpt": "Figma portfolio", "education_excerpt": "Design diploma"},
    )

    strong = _deterministic_candidate_score(application, strong_detail, {"suitability_score": 20})
    weak = _deterministic_candidate_score(application, weak_detail, {"suitability_score": 95})

    assert strong["score"] >= 60
    assert "React" in strong["matched_required"]
    assert strong["breakdown"]["location"]["priority"] == "Low"
    assert weak["score"] < 40
    assert weak["score"] < strong["score"]


def test_candidate_analysis_validation_rejects_matched_without_evidence_strength():
    raw = {
        "candidate_facts": {
            "graduation_year": 2025,
            "detected_location": {"value": "Noida", "source": "resume_header", "evidence": "Noida", "confidence": "high"},
            "total_experience_months": 10,
            "relevant_experience_months": 8,
            "education": [],
            "employment": [],
            "projects": [],
            "skills": ["Python"],
            "languages": ["Python"],
            "frameworks": [],
            "tools": [],
            "links": [],
        },
        "extraction_confidence": {"education": "unknown", "employment": "unknown", "experience_duration": "medium", "graduation_year": "high", "location": "high", "skills": "medium", "projects": "unknown"},
        "requirement_analysis": [
            {
                "requirement_id": "REQ-01",
                "requirement": "Python",
                "status": "matched",
                "evidence": [],
                "evidence_strength": "none",
                "explanation": "Unsupported match.",
            }
        ],
        "confirmed_gaps": [],
        "unclear_items": [],
        "risk_flags": [],
        "summary": "Candidate lists Python.",
        "interview_questions": [],
    }

    _, errors = _validate_candidate_analysis(raw)

    assert any("cannot be matched with none evidence" in error for error in errors)
    assert any("requires evidence" in error for error in errors)


def test_evidence_matrix_drives_score_and_track_without_graduation_year_shortcut():
    job = _job()
    application = SimpleNamespace(job=job)
    detail = SimpleNamespace(
        resume_text="B.Tech 2026. Projects: built a Flask API in Python with React frontend and PostgreSQL.",
        parsed_fields={"detected_location": "Noida", "education_excerpt": "B.Tech 2026", "projects_excerpt": "Flask API Python React PostgreSQL"},
    )
    requirements = _normalized_job_requirements(job)
    analysis_records = []
    for item in requirements["required"]:
        status = "matched" if item["category"] in {"skill", "tool", "project", "education"} else "partially_matched"
        strength = "strong" if item["criterion"] in {"Python", "Flask", "React", "PostgreSQL"} else "moderate"
        analysis_records.append(
            {
                "requirement_id": item["id"],
                "requirement": item["criterion"],
                "status": status,
                "evidence_strength": strength,
                "evidence": [{"source": "resume", "section": "Projects", "text": "built a Flask API in Python with React frontend and PostgreSQL"}],
                "explanation": "Supported by project evidence.",
            }
        )
    raw = {
        "candidate_facts": {
            "graduation_year": 2026,
            "detected_location": {"value": "Noida", "source": "resume_header", "evidence": "Noida", "confidence": "high"},
            "total_experience_months": 18,
            "relevant_experience_months": 18,
            "education": [{"degree": "B.Tech", "evidence": "B.Tech 2026"}],
            "employment": [],
            "projects": [{"name": "API", "description": "Flask API", "technologies": ["Python", "Flask"], "evidence": "Flask API"}],
            "skills": ["Python", "Flask", "React", "PostgreSQL"],
            "languages": ["Python"],
            "frameworks": ["Flask", "React"],
            "tools": ["PostgreSQL"],
            "links": [],
        },
        "extraction_confidence": {"education": "high", "employment": "unknown", "experience_duration": "medium", "graduation_year": "high", "location": "high", "skills": "high", "projects": "high"},
        "requirement_analysis": analysis_records,
        "summary": "Project evidence is relevant.",
    }

    result = _deterministic_candidate_score(application, detail, raw)

    assert result["score"] >= 55
    assert result["recommended_track"] == "Full-time"
    assert result["breakdown"]["location_preference"]["max"] == 3


def test_post_deepseek_returns_invalid_marker_for_malformed_json(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"candidate_facts\\": {},\\"requirement_analysis\\": ["}}],"usage":{"completion_tokens":4096}}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())

    test_app = create_app("testing")
    with test_app.app_context():
        test_app.config["DEEPSEEK_API_KEY"] = "test-key"
        raw, usage = _post_deepseek([], max_tokens=4096)

    assert "_invalid_json_content" in raw
    assert "Expecting" in raw["_invalid_json_error"]
    assert usage["completion_tokens"] == 4096
