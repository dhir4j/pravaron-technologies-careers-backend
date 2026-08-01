from __future__ import annotations

import os

from .auth import hash_password, normalize_email
from .extensions import db
from .models import EmailTemplate, Job, User


def seed_dev_data() -> None:
    admin_email = normalize_email(os.getenv("DEV_ADMIN_EMAIL", "admin@example.test"))
    admin_password = os.getenv("DEV_ADMIN_PASSWORD", "TestAdmin123!")
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User.query.filter_by(email=normalize_email("admin@example.test")).first()
        if admin:
            admin.email = admin_email
    if not admin:
        admin = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
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
        "verify_email": {
            "subject": "Verify your Pravaron Careers account",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "application_received": {
            "subject": "Application received",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "application_status_changed": {
            "subject": "Application status updated",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "interview_invitation": {
            "subject": "Interview invitation",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "application_withdrawn": {
            "subject": "Application withdrawn",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "position_closed": {
            "subject": "Position closed",
            "html_body": "<p>Hello {{candidate_name}},</p><p>{{message}}</p><p>Pravaron Careers</p>",
            "text_body": "Hello {{candidate_name}},\n\n{{message}}\n\nPravaron Careers",
        },
        "application_rejection": {
            "subject": "Update on your application for {{job_title}}",
            "html_body": "<h2>Application update</h2><p>Hi {{candidate_name}},</p><p>Thank you for taking the time to apply for <strong>{{job_title}}</strong> at Pravaron Technologies.</p><p>After reviewing your application, we will not be moving forward with your profile for this role at this stage.</p><p>Regards,<br />Pravaron Technologies Careers Team</p>",
            "text_body": "Hi {{candidate_name}},\n\nThank you for taking the time to apply for {{job_title}} at Pravaron Technologies.\n\nAfter reviewing your application, we will not be moving forward with your profile for this role at this stage.\n\nRegards,\nPravaron Technologies Careers Team",
        },
        "application_shortlisted": {
            "subject": "You Have Been Shortlisted for the Next Stage",
            "html_body": "<h2>You have been shortlisted</h2><p>Dear {{candidate_name}},</p><p>Thank you for applying for the <strong>{{job_title}}</strong> position at Pravaron Technologies.</p><p>We are pleased to inform you that your application has been shortlisted for the next stage of our hiring process.</p><p>The upcoming selection rounds may include:<br />Aptitude assessment<br />Role-specific technical assessment<br />Coding or practical assignment<br />Technical interview<br />Final discussion</p><p>You will receive a separate email with the assessment schedule, instructions, duration, and access details.</p><p>Please continue to monitor your registered email address for further updates.</p><p>Regards,<br />HR,<br />Pravaron Technologies<br />careers@pravarontechnologies.com</p>",
            "text_body": "Dear {{candidate_name}},\n\nThank you for applying for the {{job_title}} position at Pravaron Technologies.\n\nWe are pleased to inform you that your application has been shortlisted for the next stage of our hiring process.\n\nThe upcoming selection rounds may include:\n\nAptitude assessment\nRole-specific technical assessment\nCoding or practical assignment\nTechnical interview\nFinal discussion\n\nYou will receive a separate email with the assessment schedule, instructions, duration, and access details.\n\nPlease continue to monitor your registered email address for further updates.\n\nRegards,\nHR,\nPravaron Technologies\ncareers@pravarontechnologies.com",
        },
    }
    for key, config in templates.items():
        if not EmailTemplate.query.filter_by(key=key).first():
            db.session.add(
                EmailTemplate(
                    key=key,
                    subject=config["subject"],
                    html_body=config["html_body"],
                    text_body=config["text_body"],
                    version=1,
                    is_active=True,
                )
            )
    db.session.commit()
