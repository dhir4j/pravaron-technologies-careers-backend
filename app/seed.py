from __future__ import annotations

from .auth import hash_password, normalize_email
from .extensions import db
from .models import EmailTemplate, Job, User


def seed_dev_data() -> None:
    admin_email = normalize_email("careers@example.com")
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User.query.filter_by(email=normalize_email("admin@pravarontechnologies.com")).first()
        if admin:
            admin.email = admin_email
    if not admin:
        admin = User(
            email=admin_email,
            password_hash=hash_password("TestAdmin123!"),
            full_name="Pravaron Admin",
            role="super_admin",
            is_verified=True,
        )
        db.session.add(admin)
        db.session.flush()

    if not Job.query.filter_by(slug="agentic-ai-engineer-intern").first():
        db.session.add(
            Job(
                public_code="PRV-CAR-0001",
                title="Agentic AI Engineer Intern",
                slug="agentic-ai-engineer-intern",
                department="AI Systems",
                employment_type="Internship",
                experience_level="Student / Early Career",
                openings=3,
                location="Noida",
                workplace_model="Hybrid",
                role_summary=(
                    "Work with Pravaron Technologies on agentic AI, automation, and intelligent products "
                    "that turn manual business operations into autonomous workflows."
                ),
                responsibilities=(
                    "Prototype AI workflows, integrate APIs, evaluate outputs, document systems, and support "
                    "shipping reliable internal tools."
                ),
                required_skills=["Python", "APIs", "LLM basics", "Problem solving"],
                preferred_skills=["Flask", "Next.js", "Automation", "Data pipelines"],
                education_preference="Pursuing or recently completed a degree in computer science, engineering, or a related discipline.",
                experience_requirement="Academic, personal, or internship experience building software or AI projects.",
                source_metadata={
                    "content_sections": [
                        {
                            "id": "responsibilities",
                            "title": "What you will do",
                            "content": "Prototype AI workflows, integrate APIs, evaluate outputs, document systems, and support shipping reliable internal tools.",
                        },
                        {
                            "id": "requirements",
                            "title": "What you should bring",
                            "content": "Python\nAPIs\nLLM basics\nProblem solving",
                        },
                        {
                            "id": "preferred",
                            "title": "Useful additional experience",
                            "content": "Flask\nNext.js\nAutomation\nData pipelines",
                        },
                        {
                            "id": "education",
                            "title": "Education",
                            "content": "Pursuing or recently completed a degree in computer science, engineering, or a related discipline.",
                        },
                        {
                            "id": "experience",
                            "title": "Experience",
                            "content": "Academic, personal, or internship experience building software or AI projects.",
                        },
                    ]
                },
                status="published",
                created_by_id=admin.id,
                owner_id=admin.id,
            )
        )

    templates = {
        "verify_email": "Verify your Pravaron Careers account",
        "application_received": "Application received",
        "application_status_changed": "Application status updated",
        "interview_invitation": "Interview invitation",
        "application_withdrawn": "Application withdrawn",
        "position_closed": "Position closed",
    }
    for key, subject in templates.items():
        if not EmailTemplate.query.filter_by(key=key).first():
            db.session.add(
                EmailTemplate(
                    key=key,
                    subject=subject,
                    html_body="<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
                    text_body="Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
                    version=1,
                    is_active=True,
                )
            )
    db.session.commit()
