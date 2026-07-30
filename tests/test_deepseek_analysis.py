from __future__ import annotations

from types import SimpleNamespace

from app.deepseek_analysis import _deterministic_candidate_score


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
