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
    login(client, "admin@example.test", "TestAdmin123!")
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
    login(client, "admin@example.test", "TestAdmin123!")
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

    login(client, "admin@example.test", "TestAdmin123!")
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

    login(client, "admin@example.test", "TestAdmin123!")
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


def test_candidate_can_accept_sent_offer_and_be_marked_hired(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Candidate Offer", "email": "offer-candidate@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "offer-candidate@example.com"})
    login(client, "offer-candidate@example.com", "Secret123")
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

    login(client, "admin@example.test", "TestAdmin123!")
    offer = client.post(
        f"/api/v1/admin/applications/{application['id']}/offer",
        json={"role_title": job["title"], "department": "Engineering", "joining_date": "2026-08-01"},
    )
    assert offer.status_code == 200, offer.json
    assert offer.json["offer_letter"]["status"] == "draft"

    sent = client.post(f"/api/v1/admin/applications/{application['id']}/offer/send")
    assert sent.status_code == 200, sent.json
    assert sent.json["offer_letter"]["status"] == "sent"
    assert sent.json["application"]["candidate_status"] == "Offer Released"

    login(client, "offer-candidate@example.com", "Secret123")
    candidate_offer = client.get(f"/api/v1/candidate/applications/{application['id']}/offer")
    assert candidate_offer.status_code == 200, candidate_offer.json
    assert candidate_offer.json["offer_letter"]["role_title"] == job["title"]

    response = client.post(
        f"/api/v1/candidate/applications/{application['id']}/offer/respond",
        json={"decision": "accepted"},
    )
    assert response.status_code == 200, response.json
    assert response.json["offer_letter"]["status"] == "accepted"
    assert response.json["application"]["candidate_status"] == "Hired"

    detail = client.get(f"/api/v1/candidate/applications/{application['id']}")
    assert any(item["status"] == "Hired" for item in detail.json["application"]["timeline"])


def test_candidate_status_email_preference_is_respected(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Preference Candidate", "email": "pref-candidate@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "pref-candidate@example.com"})
    login(client, "pref-candidate@example.com", "Secret123")
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
    prefs = client.patch(
        "/api/v1/candidate/profile/notification-preferences",
        json={"email_on_status_change": False, "email_on_interview": True, "email_on_offer": True, "email_digest": False},
    )
    assert prefs.status_code == 200, prefs.json

    login(client, "admin@example.test", "TestAdmin123!")
    update = client.patch(
        f"/api/v1/admin/applications/{application['id']}/status",
        json={"internal_status": "Shortlisted", "note": "Good fit"},
    )
    assert update.status_code == 200, update.json

    login(client, "pref-candidate@example.com", "Secret123")
    notifications = client.get("/api/v1/candidate/notifications").json["notifications"]
    status_notifications = [item for item in notifications if item["notification_type"] == "application_status_changed"]
    assert any(item["channel"] == "in_app" for item in status_notifications)
    assert not any(item["channel"] == "email" for item in status_notifications)


def test_ai_interview_round_one_generates_30_mcqs_and_logs_security(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "MCQ Candidate", "email": "mcq-candidate@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "mcq-candidate@example.com"})
    login(client, "mcq-candidate@example.com", "Secret123")
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

    login(client, "admin@example.test", "TestAdmin123!")
    scheduled = client.post("/api/v1/admin/interviews/ai", json={"application_id": application["id"]})
    assert scheduled.status_code == 201, scheduled.json
    interview_id = scheduled.json["interview"]["id"]

    login(client, "mcq-candidate@example.com", "Secret123")
    started = client.post(f"/api/v1/candidate/interviews/ai/{interview_id}/start")
    assert started.status_code == 200, started.json
    assert started.json["total_questions"] == 30
    assert started.json["time_limit_seconds"] == 3600
    first = started.json["next_question"]
    assert first["category"] == "aptitude"
    assert len(first["options"]) == 4
    assert "correct_answer" not in first

    security = client.post(
        f"/api/v1/candidate/interviews/ai/{interview_id}/proctoring/event",
        json={"event_type": "tab_switch", "severity": "high", "description": "Candidate minimized window"},
    )
    assert security.status_code == 200, security.json
    assert security.json["proctoring_summary"]["tab_switches"] == 1

    answer = client.post(
        f"/api/v1/candidate/interviews/ai/{interview_id}/respond",
        json={"question_id": first["id"], "response_text": first["options"][0], "duration_seconds": 12},
    )
    assert answer.status_code == 200, answer.json
    assert answer.json["next_question"]["order"] == 2

    login(client, "admin@example.test", "TestAdmin123!")
    live = client.get(f"/api/v1/admin/interviews/ai/{interview_id}/live")
    assert live.status_code == 200, live.json
    assert live.json["status"] == "in_progress"
    assert live.json["proctoring_summary"]["tab_switches"] == 1

    message = client.post(f"/api/v1/admin/interviews/ai/{interview_id}/messages", json={"message": "Please keep your face visible."})
    assert message.status_code == 200, message.json
    assert message.json["messages"][-1]["message"] == "Please keep your face visible."


def test_ai_interview_uses_job_specific_setup_questions_and_allows_completed_delete(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Setup Candidate", "email": "setup-candidate@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "setup-candidate@example.com"})
    login(client, "setup-candidate@example.com", "Secret123")
    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    resume = client.post(
        "/api/v1/candidate/resumes",
        data={"resume": (io.BytesIO(b"%PDF-1.4 setup resume"), "resume.pdf")},
        content_type="multipart/form-data",
    ).json["resume"]
    application = client.post(
        "/api/v1/candidate/applications",
        json={"job_id": job["id"], "resume_id": resume["id"], "declarations": {"accuracy": True, "privacy": True}},
    ).json["application"]

    login(client, "admin@example.test", "TestAdmin123!")
    setup_question = client.post(
        "/api/v1/admin/interviews/setup/questions",
        json={
            "job_id": job["id"],
            "mode": "mcq",
            "category": "technical",
            "content": "Which custom setup answer should appear for this job-specific technical MCQ?",
            "options": ["Custom answer", "Fallback answer", "No answer", "Wrong answer"],
            "correct_answer": "Custom answer",
        },
    )
    assert setup_question.status_code == 201, setup_question.json

    scheduled = client.post("/api/v1/admin/interviews/ai", json={"application_id": application["id"]})
    assert scheduled.status_code == 201, scheduled.json
    interview_id = scheduled.json["interview"]["id"]

    login(client, "setup-candidate@example.com", "Secret123")
    started = client.post(f"/api/v1/candidate/interviews/ai/{interview_id}/start")
    assert started.status_code == 200, started.json
    questions = client.get(f"/api/v1/candidate/interviews/ai/{interview_id}").json["interview"]["questions"]
    technical_questions = [question for question in questions if question["category"] == "technical"]
    assert technical_questions[0]["content"] == "Which custom setup answer should appear for this job-specific technical MCQ?"

    for question in questions:
        selected = "Custom answer" if question["content"] == "Which custom setup answer should appear for this job-specific technical MCQ?" else question["options"][0]
        response = client.post(
            f"/api/v1/candidate/interviews/ai/{interview_id}/respond",
            json={"question_id": question["id"], "response_text": selected, "duration_seconds": 2},
        )
        assert response.status_code == 200, response.json
    completed = client.post(f"/api/v1/candidate/interviews/ai/{interview_id}/complete")
    assert completed.status_code == 200, completed.json
    assert completed.json["interview"]["ai_scores"]["score_out_of_100"] >= 0

    login(client, "admin@example.test", "TestAdmin123!")
    deleted = client.delete(f"/api/v1/admin/interviews/ai/{interview_id}")
    assert deleted.status_code == 200, deleted.json


def test_application_group_batch_email_creates_group_sends_and_updates_status(client, monkeypatch):
    from app import routes as route_module

    monkeypatch.setattr(route_module, "send_email", lambda *args, **kwargs: True)
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Group Candidate", "email": "group-candidate@example.com", "password": "Secret123"},
    )
    client.post("/api/v1/auth/dev-verify", json={"email": "group-candidate@example.com"})
    login(client, "group-candidate@example.com", "Secret123")
    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    resume = client.post(
        "/api/v1/candidate/resumes",
        data={"resume": (io.BytesIO(b"%PDF-1.4 group resume"), "resume.pdf")},
        content_type="multipart/form-data",
    ).json["resume"]
    application = client.post(
        "/api/v1/candidate/applications",
        json={"job_id": job["id"], "resume_id": resume["id"], "declarations": {"accuracy": True, "privacy": True}},
    ).json["application"]

    login(client, "admin@example.test", "TestAdmin123!")
    created = client.post(
        "/api/v1/admin/application-groups",
        json={"name": "Shortlist batch", "application_ids": [application["id"]]},
    )
    assert created.status_code == 201, created.json
    group = created.json["group"]
    assert group["member_count"] == 1

    sent = client.post(
        f"/api/v1/admin/application-groups/{group['id']}/send-email",
        json={
            "purpose": "Selection update",
            "status_to_apply": "Shortlisted",
            "subject": "Status for {{candidate_name}}",
            "text_body": "Hi {{candidate_name}}, status: {{application_status}} for {{job_title}}",
            "html_body": "<p>Hi {{candidate_name}}, status: {{application_status}}</p>",
        },
    )
    assert sent.status_code == 200, sent.json
    assert sent.json["sent"] == 1
    assert sent.json["failed"] == 0

    detail = client.get(f"/api/v1/admin/application-groups/{group['id']}")
    assert detail.status_code == 200, detail.json
    assert detail.json["group"]["emails"][0]["delivery_status"] == "sent"

    updated = client.get(f"/api/v1/admin/applications/{application['id']}")
    assert updated.json["application"]["internal_status"] == "Shortlisted"

def test_mail_sync_does_not_full_rebuild_details_by_default(client, monkeypatch):
    from app import routes as route_module

    login(client, "admin@example.test", "TestAdmin123!")
    monkeypatch.setattr(
        route_module,
        "sync_careers_mailbox",
        lambda actor, limit=None: {
            "mailbox": "INBOX",
            "checked": 1,
            "imported": 0,
            "skipped_duplicate": 1,
            "skipped_existing_application": 0,
            "skipped_unrelated": 0,
            "skipped_unreadable": 0,
            "errors": [],
            "application_ids": [],
        },
    )
    monkeypatch.setattr(route_module, "rebuild_applicant_details", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad stored resume")))

    response = client.post("/api/v1/admin/applications/sync-mail")

    assert response.status_code == 200, response.json
    assert response.json["sync"]["checked"] == 1
    assert "detail_rebuild" not in response.json["sync"]


def test_mail_sync_explicit_detail_rebuild_returns_warning_instead_of_500(client, monkeypatch):
    from app import routes as route_module

    login(client, "admin@example.test", "TestAdmin123!")
    monkeypatch.setattr(
        route_module,
        "sync_careers_mailbox",
        lambda actor, limit=None: {
            "mailbox": "INBOX",
            "checked": 1,
            "imported": 0,
            "skipped_duplicate": 1,
            "skipped_existing_application": 0,
            "skipped_unrelated": 0,
            "skipped_unreadable": 0,
            "errors": [],
            "application_ids": [],
        },
    )
    monkeypatch.setattr(route_module, "rebuild_applicant_details", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad stored resume")))

    response = client.post("/api/v1/admin/applications/sync-mail", json={"rebuild_details": True})

    assert response.status_code == 200, response.json
    assert response.json["sync"]["detail_rebuild"]["failed"] == 1
    assert "bad stored resume" in response.json["sync"]["detail_rebuild"]["errors"][0]["error"]

def test_existing_group_batch_email_only_targets_newly_added_members(client, monkeypatch):
    from app import routes as route_module

    sent_to: list[str] = []
    monkeypatch.setattr(route_module, "send_email", lambda to, *args, **kwargs: sent_to.append(to) or True)

    job = client.get("/api/v1/public/jobs").json["jobs"][0]
    application_ids = []
    for index in range(2):
        email = f"group-later-{index}@example.com"
        client.post("/api/v1/auth/register", json={"full_name": f"Group Later {index}", "email": email, "password": "Secret123"})
        client.post("/api/v1/auth/dev-verify", json={"email": email})
        login(client, email, "Secret123")
        resume = client.post(
            "/api/v1/candidate/resumes",
            data={"resume": (io.BytesIO(b"%PDF-1.4 group later resume"), f"resume-{index}.pdf")},
            content_type="multipart/form-data",
        ).json["resume"]
        application = client.post(
            "/api/v1/candidate/applications",
            json={"job_id": job["id"], "resume_id": resume["id"], "declarations": {"accuracy": True, "privacy": True}},
        ).json["application"]
        application_ids.append(application["id"])

    login(client, "admin@example.test", "TestAdmin123!")
    created = client.post("/api/v1/admin/application-groups", json={"name": "Rolling shortlist", "application_ids": [application_ids[0]]})
    assert created.status_code == 201, created.json
    group_id = created.json["group"]["id"]

    first_send = client.post(
        f"/api/v1/admin/application-groups/{group_id}/send-email",
        json={"subject": "First update", "text_body": "Hi {{candidate_name}}", "application_ids": [application_ids[0]]},
    )
    assert first_send.status_code == 200, first_send.json
    assert sent_to == ["group-later-0@example.com"]

    added = client.post(f"/api/v1/admin/application-groups/{group_id}/members", json={"application_ids": application_ids})
    assert added.status_code == 200, added.json
    assert added.json["added"] == 1
    assert added.json["added_application_ids"] == [application_ids[1]]

    second_send = client.post(
        f"/api/v1/admin/application-groups/{group_id}/send-email",
        json={"subject": "Second update", "text_body": "Hi {{candidate_name}}", "application_ids": added.json["added_application_ids"]},
    )
    assert second_send.status_code == 200, second_send.json
    assert second_send.json["sent"] == 1
    assert sent_to == ["group-later-0@example.com", "group-later-1@example.com"]
