from __future__ import annotations

import io

import pytest
from sqlalchemy import Text

from app import create_app
from app.extensions import db
from app.models import Job
from app.seed import seed_dev_data


@pytest.fixture()
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        seed_dev_data()
    return app.test_client()


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.json
    return response


def test_public_jobs_are_listed(client):
    response = client.get("/api/v1/public/jobs")
    assert response.status_code == 200
    assert response.json["jobs"][0]["slug"] == "agentic-ai-engineer-intern"


def test_public_openings_feed_has_direct_careers_links(client):
    response = client.get("/api/v1/public/openings")
    assert response.status_code == 200
    assert response.json["count"] == 1
    opening = response.json["openings"][0]
    assert opening["title"] == "Agentic AI Engineer Intern"
    assert opening["job_id"] == "PRV-CAR-0001"
    assert opening["url"].endswith("/jobs/PRV-CAR-0001/agentic-ai-engineer-intern")
    assert "selection_process" not in opening

    json_alias = client.get("/api/v1/public/openings.json")
    assert json_alias.status_code == 200
    assert json_alias.json == response.json


def test_admin_can_manage_public_job_content_sections(client):
    login(client, "careers@example.com", "TestAdmin123!")
    response = client.post(
        "/api/v1/admin/jobs",
        json={
            "title": "Platform Engineer",
            "role_summary": "Build reliable automation platforms.",
            "status": "published",
            "education_preference": "Bachelor's degree or equivalent practical experience.",
            "experience_requirement": "Two years building production software.",
            "application_status_text": "Applications reviewed weekly",
            "content_sections": [
                {"id": "responsibilities", "title": "What you will build", "content": "Reliable services"},
                {"id": "education", "title": "Education", "content": "Degree or equivalent experience"},
                {"id": "custom-security", "title": "Security mindset", "content": "Design for least privilege"},
            ],
        },
    )
    assert response.status_code == 201, response.json
    job = response.json["job"]
    assert job["public_code"].startswith("PRV-CAR-")
    assert job["application_status_text"] == "Applications reviewed weekly"
    assert [section["title"] for section in job["content_sections"]] == [
        "What you will build",
        "Education",
        "Security mindset",
    ]

    detail = client.get(f"/api/v1/public/jobs/{job['slug']}")
    assert detail.status_code == 200
    assert detail.json["job"]["public_code"] == job["public_code"]
    assert detail.json["job"]["content_sections"][2]["content"] == "Design for least privilege"


def test_job_long_form_requirements_are_text_columns():
    assert isinstance(Job.__table__.c.education_preference.type, Text)
    assert isinstance(Job.__table__.c.experience_requirement.type, Text)


def test_admin_can_pause_and_delete_job_without_applications(client):
    login(client, "careers@example.com", "TestAdmin123!")
    created = client.post(
        "/api/v1/admin/jobs",
        json={"title": "Temporary Role", "role_summary": "Short lived role.", "status": "published"},
    )
    assert created.status_code == 201, created.json
    job_id = created.json["job"]["id"]

    paused = client.patch(f"/api/v1/admin/jobs/{job_id}", json={"status": "paused"})
    assert paused.status_code == 200, paused.json
    assert paused.json["job"]["status"] == "paused"

    deleted = client.delete(f"/api/v1/admin/jobs/{job_id}")
    assert deleted.status_code == 204
    listing = client.get("/api/v1/admin/jobs")
    assert all(job["id"] != job_id for job in listing.json["jobs"])


def test_admin_cannot_delete_job_with_applications(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Candidate Three", "email": "candidate3@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "candidate3@example.com"})
    login(client, "candidate3@example.com", "Secret123")
    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    resume = client.post(
        "/api/v1/candidate/resumes",
        data={"resume": (io.BytesIO(b"%PDF-1.4 test resume"), "resume.pdf")},
        content_type="multipart/form-data",
    ).json["resume"]
    applied = client.post(
        "/api/v1/candidate/applications",
        json={"job_id": job["id"], "resume_id": resume["id"], "declarations": {"accuracy": True, "privacy": True}},
    )
    assert applied.status_code == 201, applied.json

    login(client, "careers@example.com", "TestAdmin123!")
    deleted = client.delete(f"/api/v1/admin/jobs/{job['id']}")
    assert deleted.status_code == 409
    assert "cannot be deleted" in deleted.json["error"]


def test_candidate_can_apply_once_and_get_notification(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Candidate One", "email": "candidate@example.com", "password": "Secret123"},
    )
    assert response.status_code == 201
    client.post("/api/v1/auth/dev-verify", json={"email": "candidate@example.com"})
    login(client, "candidate@example.com", "Secret123")

    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    resume_response = client.post(
        "/api/v1/candidate/resumes",
        data={"resume": (io.BytesIO(b"%PDF-1.4 test resume"), "resume.pdf")},
        content_type="multipart/form-data",
    )
    assert resume_response.status_code == 201, resume_response.json

    application_response = client.post(
        "/api/v1/candidate/applications",
        json={
            "job_id": job["id"],
            "resume_id": resume_response.json["resume"]["id"],
            "cover_message": "I want to build agentic systems.",
            "answers": {},
            "declarations": {"accuracy": True, "privacy": True},
            "source": "careers-site",
        },
    )
    assert application_response.status_code == 201, application_response.json

    duplicate_response = client.post(
        "/api/v1/candidate/applications",
        json={
            "job_id": job["id"],
            "resume_id": resume_response.json["resume"]["id"],
            "declarations": {"accuracy": True, "privacy": True},
        },
    )
    assert duplicate_response.status_code == 409

    notifications = client.get("/api/v1/candidate/notifications")
    assert notifications.status_code == 200
    assert notifications.json["notifications"][0]["notification_type"] == "application_submitted"


def test_admin_can_update_status_and_candidate_sees_timeline(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Candidate Two", "email": "candidate2@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "candidate2@example.com"})
    login(client, "candidate2@example.com", "Secret123")
    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    resume = client.post(
        "/api/v1/candidate/resumes",
        data={"resume": (io.BytesIO(b"%PDF-1.4 test resume"), "resume.pdf")},
        content_type="multipart/form-data",
    ).json["resume"]
    application = client.post(
        "/api/v1/candidate/applications",
        json={"job_id": job["id"], "resume_id": resume["id"], "declarations": {"accuracy": True, "privacy": True}},
    ).json["application"]

    login(client, "careers@example.com", "TestAdmin123!")
    update = client.patch(
        f"/api/v1/admin/applications/{application['id']}/status",
        json={"internal_status": "Shortlisted", "note": "Good fit"},
    )
    assert update.status_code == 200, update.json
    assert update.json["application"]["candidate_status"] == "Shortlisted"

    login(client, "candidate2@example.com", "Secret123")
    detail = client.get(f"/api/v1/candidate/applications/{application['id']}")
    assert detail.status_code == 200
    assert any(item["status"] == "Shortlisted" for item in detail.json["application"]["timeline"])
