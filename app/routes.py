from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from .auth import (
    ADMIN_ROLES,
    REVIEWER_ROLES,
    clear_auth_cookie,
    create_action_token,
    hash_password,
    load_action_token,
    mark_login,
    normalize_email,
    password_is_valid,
    require_auth,
    require_roles,
    serialize_user,
    set_auth_cookie,
    verify_password,
)
from .extensions import db
from .models import (
    Application,
    ApplicationEvent,
    CandidateProfile,
    EmailTemplate,
    InternalNote,
    Interview,
    Job,
    Notification,
    ReviewScorecard,
    ReviewerAssignment,
    Resume,
    User,
    utcnow,
)
from .serializers import (
    application_to_dict,
    interview_to_dict,
    job_to_dict,
    notification_to_dict,
    profile_to_dict,
    resume_to_dict,
    user_to_dict,
)
from .services import (
    create_audit,
    create_notification,
    job_accepts_applications,
    next_public_code,
    parse_datetime,
    save_resume_file,
    slugify,
    update_application_status,
)

api = Blueprint("api", __name__)


def json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def payload() -> dict:
    return request.get_json(silent=True) or {}


def normalize_content_sections(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    sections = []
    for index, item in enumerate(value[:30]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:160]
        content = str(item.get("content") or "").strip()
        if not title:
            continue
        sections.append(
            {
                "id": str(item.get("id") or f"section-{index + 1}")[:80],
                "title": title,
                "content": content,
            }
        )
    return sections


def job_source_metadata(data: dict, existing: dict | None = None) -> dict:
    metadata = dict(existing or {})
    submitted_metadata = data.get("source_metadata")
    if isinstance(submitted_metadata, dict):
        metadata.update(submitted_metadata)
    if "content_sections" in data:
        metadata["content_sections"] = normalize_content_sections(data["content_sections"])
    elif "content_sections" in metadata:
        metadata["content_sections"] = normalize_content_sections(metadata["content_sections"])
    if "application_status_text" in data:
        metadata["application_status_text"] = str(data["application_status_text"] or "").strip()[:120]
    return metadata


def can_view_application(user: User, application: Application) -> bool:
    if user.role in ADMIN_ROLES:
        return True
    if application.candidate_id == user.id:
        return True
    if user.role in REVIEWER_ROLES:
        return (
            ReviewerAssignment.query.filter_by(reviewer_id=user.id, application_id=application.id).first()
            or ReviewerAssignment.query.filter_by(reviewer_id=user.id, job_id=application.job_id).first()
        )
    return False


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/auth/register")
def register():
    data = payload()
    email = normalize_email(data.get("email", ""))
    password = data.get("password", "")
    full_name = (data.get("full_name") or "").strip()
    if not email or not password or not full_name:
        return json_error("full_name, email, and password are required")
    if not password_is_valid(password):
        return json_error("Password must be at least 8 characters and include a letter and a number")
    user = User(email=email, password_hash=hash_password(password), full_name=full_name, role="candidate", is_verified=False)
    user.profile = CandidateProfile()
    db.session.add(user)
    try:
        create_audit("auth.registered", "user", user.id, user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("An account with this email already exists", 409)
    return jsonify({"user": serialize_user(user), "message": "Registration successful. Verify email before applying."}), 201


@api.post("/auth/login")
def login():
    data = payload()
    email = normalize_email(data.get("email", ""))
    password = data.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(user.password_hash, password):
        return json_error("Invalid email or password", 401)
    if not user.is_active:
        return json_error("Account is inactive", 403)
    mark_login(user)
    create_audit("auth.login", "user", user.id, user)
    db.session.commit()
    response = jsonify({"user": serialize_user(user)})
    return set_auth_cookie(response, user)


@api.post("/auth/request-verification")
def request_verification():
    user = User.query.filter_by(email=normalize_email(payload().get("email", ""))).first()
    if user and not user.is_verified:
        token = create_action_token(user, "verify_email")
        create_notification(
            user.id,
            "Verify your Pravaron Careers account",
            "Use the verification link sent to your email to activate your account.",
            "verify_email",
            channel="email",
        )
        create_audit("auth.verification_requested", "user", user.id, user)
        db.session.commit()
        response = {"message": "If the account exists, a verification email has been queued."}
        if current_app.config["APP_ENV"] != "production":
            response["verification_token"] = token
        return jsonify(response)
    return jsonify({"message": "If the account exists, a verification email has been queued."})


@api.post("/auth/verify-email")
def verify_email():
    token = payload().get("token")
    user = load_action_token(token or "", "verify_email", 60 * 60 * 24)
    if not user:
        return json_error("Invalid or expired verification token", 400)
    user.is_verified = True
    create_audit("auth.email_verified", "user", user.id, user)
    db.session.commit()
    return jsonify({"message": "Email verified"})


@api.post("/auth/forgot-password")
def forgot_password():
    user = User.query.filter_by(email=normalize_email(payload().get("email", ""))).first()
    if user:
        token = create_action_token(user, "reset_password")
        create_notification(
            user.id,
            "Reset your Pravaron Careers password",
            "Use the password reset link sent to your email.",
            "password_reset",
            channel="email",
        )
        create_audit("auth.password_reset_requested", "user", user.id, user)
        db.session.commit()
        response = {"message": "If the account exists, a reset email has been queued."}
        if current_app.config["APP_ENV"] != "production":
            response["reset_token"] = token
        return jsonify(response)
    return jsonify({"message": "If the account exists, a reset email has been queued."})


@api.post("/auth/reset-password")
def reset_password():
    data = payload()
    user = load_action_token(data.get("token") or "", "reset_password", 60 * 60)
    if not user:
        return json_error("Invalid or expired reset token", 400)
    if not password_is_valid(data.get("password", "")):
        return json_error("Password must be at least 8 characters and include a letter and a number")
    user.password_hash = hash_password(data["password"])
    create_audit("auth.password_reset_completed", "user", user.id, user)
    db.session.commit()
    return jsonify({"message": "Password reset successful"})


@api.post("/auth/logout")
@require_auth
def logout():
    response = jsonify({"message": "Logged out"})
    return clear_auth_cookie(response)


@api.get("/auth/me")
@require_auth
def me():
    return jsonify({"user": user_to_dict(g.user)})


@api.post("/auth/dev-verify")
def dev_verify_email():
    data = payload()
    user = User.query.filter_by(email=normalize_email(data.get("email", ""))).first()
    if not user:
        return json_error("User not found", 404)
    user.is_verified = True
    create_audit("auth.email_verified", "user", user.id, user)
    db.session.commit()
    return jsonify({"message": "Email verified"})


@api.get("/public/jobs")
def public_jobs():
    query = Job.query.filter_by(status="published")
    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Job.title.ilike(like), Job.department.ilike(like), Job.role_summary.ilike(like)))
    for field in ["department", "employment_type", "experience_level", "location", "workplace_model"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(Job, field) == value)
    jobs = query.order_by(Job.created_at.desc()).all()
    return jsonify({"jobs": [job_to_dict(job) for job in jobs]})


@api.get("/public/openings")
@api.get("/public/openings.json")
def public_openings():
    jobs = Job.query.filter_by(status="published").order_by(Job.created_at.desc()).all()
    careers_url = current_app.config["CAREERS_PUBLIC_URL"]
    return jsonify(
        {
            "openings": [
                {
                    "id": job.id,
                    "code": job.public_code,
                    "job_id": job.public_code,
                    "title": job.title,
                    "department": job.department,
                    "employment_type": job.employment_type,
                    "experience_level": job.experience_level,
                    "location": job.location,
                    "workplace_model": job.workplace_model,
                    "summary": job.role_summary,
                    "url": f"{careers_url}/jobs/{job.public_code}/{job.slug}",
                    "published_at": (job.publish_at or job.created_at).isoformat(),
                }
                for job in jobs
            ],
            "careers_url": careers_url,
            "count": len(jobs),
        }
    )


@api.get("/public/jobs/<slug>")
def public_job_detail(slug: str):
    job = Job.query.filter_by(slug=slug, status="published").first()
    if not job:
        return json_error("Job not found", 404)
    return jsonify({"job": job_to_dict(job)})


@api.get("/candidate/profile")
@require_roles("candidate")
def get_candidate_profile():
    return jsonify({"profile": profile_to_dict(g.user.profile), "user": serialize_user(g.user)})


@api.patch("/candidate/profile")
@require_roles("candidate")
def update_candidate_profile():
    data = payload()
    profile = g.user.profile or CandidateProfile(user_id=g.user.id)
    allowed = {
        "phone",
        "current_city",
        "state",
        "country",
        "preferred_work_location",
        "current_role",
        "total_experience_years",
        "current_company",
        "notice_period",
        "current_compensation",
        "expected_compensation",
        "skills",
        "linkedin_url",
        "github_url",
        "portfolio_url",
        "personal_website_url",
        "metadata",
    }
    for key in allowed:
        if key in data:
            if key == "metadata":
                profile.extra_metadata = data[key]
            else:
                setattr(profile, key, data[key])
    db.session.add(profile)
    create_audit("candidate.profile_updated", "candidate_profile", profile.id, g.user)
    db.session.commit()
    return jsonify({"profile": profile_to_dict(profile)})


@api.post("/candidate/resumes")
@require_roles("candidate")
def upload_resume():
    upload = request.files.get("resume")
    if not upload:
        return json_error("resume file is required")
    try:
        resume = save_resume_file(g.user, upload)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return json_error(str(exc))
    return jsonify({"resume": resume_to_dict(resume)}), 201


@api.get("/candidate/resumes")
@require_roles("candidate")
def list_resumes():
    resumes = Resume.query.filter_by(user_id=g.user.id).order_by(Resume.created_at.desc()).all()
    return jsonify({"resumes": [resume_to_dict(resume) for resume in resumes]})


@api.post("/candidate/applications")
@require_roles("candidate")
def submit_application():
    if not g.user.is_verified:
        return json_error("Verify email before applying", 403)
    data = payload()
    job = db.session.get(Job, data.get("job_id"))
    if not job:
        return json_error("Job not found", 404)
    if not job_accepts_applications(job):
        return json_error("Job is not accepting applications", 409)
    resume_id = data.get("resume_id")
    resume = db.session.get(Resume, resume_id) if resume_id else None
    if not resume or resume.user_id != g.user.id:
        return json_error("A valid resume_id is required")
    declarations = data.get("declarations") or {}
    if not declarations.get("accuracy") or not declarations.get("privacy"):
        return json_error("Required declarations must be accepted")
    application = Application(
        candidate_id=g.user.id,
        job_id=job.id,
        resume_id=resume.id,
        cover_message=data.get("cover_message"),
        answers=data.get("answers") or {},
        declarations=declarations,
        source=data.get("source"),
    )
    db.session.add(application)
    try:
        db.session.flush()
        db.session.add(
            ApplicationEvent(
                application_id=application.id,
                actor_id=g.user.id,
                event_type="application_submitted",
                new_status=application.internal_status,
                visible_to_candidate=True,
            )
        )
        create_notification(
            g.user.id,
            "Application submitted",
            f"Your application for {job.title} has been submitted.",
            "application_submitted",
            application.id,
        )
        create_audit("application.submitted", "application", application.id, g.user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("You have already applied for this job", 409)
    return jsonify({"application": application_to_dict(application)}), 201


@api.get("/candidate/applications")
@require_roles("candidate")
def candidate_applications():
    applications = Application.query.filter_by(candidate_id=g.user.id).order_by(Application.created_at.desc()).all()
    return jsonify({"applications": [application_to_dict(item) for item in applications]})


@api.get("/candidate/applications/<application_id>")
@require_roles("candidate")
def candidate_application_detail(application_id: str):
    application = db.session.get(Application, application_id)
    if not application or application.candidate_id != g.user.id:
        return json_error("Application not found", 404)
    events = (
        ApplicationEvent.query.filter_by(application_id=application.id, visible_to_candidate=True)
        .order_by(ApplicationEvent.created_at.asc())
        .all()
    )
    data = application_to_dict(application)
    data["timeline"] = [
        {"event_type": event.event_type, "status": event.new_status, "note": event.note, "created_at": event.created_at.isoformat()}
        for event in events
    ]
    return jsonify({"application": data})


@api.post("/candidate/applications/<application_id>/withdraw")
@require_roles("candidate")
def withdraw_application(application_id: str):
    application = db.session.get(Application, application_id)
    if not application or application.candidate_id != g.user.id:
        return json_error("Application not found", 404)
    if application.internal_status in {"Withdrawn", "Hired", "Rejected"}:
        return json_error("Application cannot be withdrawn from its current status", 409)
    application.withdrawn_at = utcnow()
    application.withdrawal_reason = payload().get("reason")
    update_application_status(application, "Withdrawn", g.user, application.withdrawal_reason)
    db.session.commit()
    return jsonify({"application": application_to_dict(application)})


@api.get("/candidate/notifications")
@require_roles("candidate")
def candidate_notifications():
    items = Notification.query.filter_by(recipient_id=g.user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return jsonify({"notifications": [notification_to_dict(item) for item in items]})


@api.patch("/candidate/notifications/<notification_id>/read")
@require_auth
def mark_notification_read(notification_id: str):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.recipient_id != g.user.id:
        return json_error("Notification not found", 404)
    notification.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"notification": notification_to_dict(notification)})


@api.get("/admin/dashboard")
@require_roles(*ADMIN_ROLES)
def admin_dashboard():
    today = datetime.now(timezone.utc).date()
    applications = Application.query
    metrics = {
        "open_jobs": Job.query.filter_by(status="published").count(),
        "active_applications": applications.filter(Application.internal_status.notin_(["Rejected", "Withdrawn", "Hired"])).count(),
        "new_applications_today": applications.filter(db.func.date(Application.created_at) == today).count(),
        "awaiting_review": applications.filter(Application.internal_status.in_(["New", "Assigned for Review"])).count(),
        "shortlisted": applications.filter_by(internal_status="Shortlisted").count(),
        "interviews_scheduled": Interview.query.filter_by(status="Invitation Sent").count(),
        "offers_released": applications.filter_by(internal_status="Offer Sent").count(),
        "hires_completed": applications.filter_by(internal_status="Hired").count(),
    }
    return jsonify({"metrics": metrics})


@api.get("/admin/jobs")
@require_roles(*ADMIN_ROLES)
def admin_jobs():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return jsonify({"jobs": [job_to_dict(job, include_private=True) for job in jobs]})


@api.post("/admin/jobs")
@require_roles(*ADMIN_ROLES)
def create_job():
    data = payload()
    if not data.get("title") or not data.get("role_summary"):
        return json_error("title and role_summary are required")
    base_slug = data.get("slug") or slugify(data["title"])
    slug = base_slug
    suffix = 2
    while Job.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    job = Job(
        public_code=data.get("public_code") or next_public_code(),
        title=data["title"],
        slug=slug,
        department=data.get("department"),
        employment_type=data.get("employment_type") or "Full-time",
        experience_level=data.get("experience_level"),
        openings=data.get("openings") or 1,
        location=data.get("location"),
        workplace_model=data.get("workplace_model") or "Hybrid",
        salary_display=data.get("salary_display") or "hidden",
        min_salary=data.get("min_salary"),
        max_salary=data.get("max_salary"),
        currency=data.get("currency") or "INR",
        role_summary=data["role_summary"],
        responsibilities=data.get("responsibilities"),
        required_skills=data.get("required_skills") or [],
        preferred_skills=data.get("preferred_skills") or [],
        education_preference=data.get("education_preference"),
        experience_requirement=data.get("experience_requirement"),
        application_questions=data.get("application_questions") or [],
        selection_process=data.get("selection_process"),
        application_deadline=parse_datetime(data.get("application_deadline")),
        publish_at=parse_datetime(data.get("publish_at")),
        owner_id=data.get("owner_id"),
        created_by_id=g.user.id,
        status=data.get("status") or "draft",
        source_metadata=job_source_metadata(data),
    )
    db.session.add(job)
    db.session.flush()
    create_audit("job.created", "job", job.id, g.user)
    db.session.commit()
    return jsonify({"job": job_to_dict(job, include_private=True)}), 201


@api.patch("/admin/jobs/<job_id>")
@require_roles(*ADMIN_ROLES)
def update_job(job_id: str):
    job = db.session.get(Job, job_id)
    if not job:
        return json_error("Job not found", 404)
    data = payload()
    mutable = {
        "title",
        "department",
        "employment_type",
        "experience_level",
        "openings",
        "location",
        "workplace_model",
        "salary_display",
        "min_salary",
        "max_salary",
        "currency",
        "role_summary",
        "responsibilities",
        "required_skills",
        "preferred_skills",
        "education_preference",
        "experience_requirement",
        "application_questions",
        "selection_process",
        "owner_id",
        "status",
    }
    for key in mutable:
        if key in data:
            setattr(job, key, data[key])
    if "content_sections" in data or "application_status_text" in data or "source_metadata" in data:
        job.source_metadata = job_source_metadata(data, job.source_metadata)
    if "application_deadline" in data:
        job.application_deadline = parse_datetime(data.get("application_deadline"))
    if "publish_at" in data:
        job.publish_at = parse_datetime(data.get("publish_at"))
    create_audit("job.updated", "job", job.id, g.user, {"fields": sorted(data.keys())})
    db.session.commit()
    return jsonify({"job": job_to_dict(job, include_private=True)})


@api.post("/admin/jobs/<job_id>/duplicate")
@require_roles(*ADMIN_ROLES)
def duplicate_job(job_id: str):
    source = db.session.get(Job, job_id)
    if not source:
        return json_error("Job not found", 404)
    clone = Job(
        public_code=next_public_code(),
        title=f"{source.title} Copy",
        slug=f"{source.slug}-copy-{int(datetime.now().timestamp())}",
        department=source.department,
        employment_type=source.employment_type,
        experience_level=source.experience_level,
        openings=source.openings,
        location=source.location,
        workplace_model=source.workplace_model,
        salary_display=source.salary_display,
        min_salary=source.min_salary,
        max_salary=source.max_salary,
        currency=source.currency,
        role_summary=source.role_summary,
        responsibilities=source.responsibilities,
        required_skills=source.required_skills,
        preferred_skills=source.preferred_skills,
        education_preference=source.education_preference,
        experience_requirement=source.experience_requirement,
        application_questions=source.application_questions,
        selection_process=source.selection_process,
        source_metadata=dict(source.source_metadata or {}),
        created_by_id=g.user.id,
        status="draft",
    )
    db.session.add(clone)
    db.session.flush()
    create_audit("job.duplicated", "job", clone.id, g.user, {"source_job_id": source.id})
    db.session.commit()
    return jsonify({"job": job_to_dict(clone, include_private=True)}), 201


@api.get("/admin/applications")
@require_roles(*REVIEWER_ROLES)
def admin_applications():
    query = Application.query.join(Job).join(User, Application.candidate_id == User.id)
    if g.user.role not in ADMIN_ROLES:
        assigned_application_ids = [a.application_id for a in ReviewerAssignment.query.filter_by(reviewer_id=g.user.id).all() if a.application_id]
        assigned_job_ids = [a.job_id for a in ReviewerAssignment.query.filter_by(reviewer_id=g.user.id).all() if a.job_id]
        query = query.filter(or_(Application.id.in_(assigned_application_ids), Application.job_id.in_(assigned_job_ids)))
    if request.args.get("status"):
        query = query.filter(Application.internal_status == request.args["status"])
    if request.args.get("job_id"):
        query = query.filter(Application.job_id == request.args["job_id"])
    if request.args.get("search"):
        like = f"%{request.args['search']}%"
        query = query.filter(or_(User.full_name.ilike(like), User.email.ilike(like), Job.title.ilike(like), Application.id.ilike(like)))
    items = query.order_by(Application.created_at.desc()).all()
    return jsonify({"applications": [application_to_dict(item, include_private=True) for item in items]})


@api.get("/admin/applications/<application_id>")
@require_roles(*REVIEWER_ROLES)
def admin_application_detail(application_id: str):
    application = db.session.get(Application, application_id)
    if not application or not can_view_application(g.user, application):
        return json_error("Application not found", 404)
    data = application_to_dict(application, include_private=True)
    data["events"] = [
        {
            "event_type": event.event_type,
            "previous_status": event.previous_status,
            "new_status": event.new_status,
            "note": event.note,
            "visible_to_candidate": event.visible_to_candidate,
            "created_at": event.created_at.isoformat(),
        }
        for event in ApplicationEvent.query.filter_by(application_id=application.id).order_by(ApplicationEvent.created_at.asc()).all()
    ]
    data["notes"] = [
        {"id": note.id, "author_id": note.author_id, "body": note.body, "created_at": note.created_at.isoformat()}
        for note in InternalNote.query.filter_by(application_id=application.id).order_by(InternalNote.created_at.desc()).all()
    ]
    return jsonify({"application": data})


@api.patch("/admin/applications/<application_id>/status")
@require_roles(*ADMIN_ROLES)
def admin_update_application_status(application_id: str):
    application = db.session.get(Application, application_id)
    if not application:
        return json_error("Application not found", 404)
    data = payload()
    if not data.get("internal_status"):
        return json_error("internal_status is required")
    update_application_status(application, data["internal_status"], g.user, data.get("note"), data.get("rejection_reason"))
    db.session.commit()
    return jsonify({"application": application_to_dict(application, include_private=True)})


@api.post("/admin/applications/<application_id>/notes")
@require_roles(*REVIEWER_ROLES)
def add_note(application_id: str):
    application = db.session.get(Application, application_id)
    if not application or not can_view_application(g.user, application):
        return json_error("Application not found", 404)
    body = (payload().get("body") or "").strip()
    if not body:
        return json_error("body is required")
    note = InternalNote(application_id=application.id, author_id=g.user.id, body=body)
    db.session.add(note)
    create_audit("application.note_added", "application", application.id, g.user)
    db.session.commit()
    return jsonify({"note": {"id": note.id, "body": note.body, "created_at": note.created_at.isoformat()}}), 201


@api.post("/admin/applications/<application_id>/assignments")
@require_roles(*ADMIN_ROLES)
def assign_reviewer(application_id: str):
    application = db.session.get(Application, application_id)
    reviewer = db.session.get(User, payload().get("reviewer_id"))
    if not application:
        return json_error("Application not found", 404)
    if not reviewer or reviewer.role not in REVIEWER_ROLES:
        return json_error("Reviewer not found", 404)
    assignment = ReviewerAssignment(application_id=application.id, reviewer_id=reviewer.id, assigned_by_id=g.user.id)
    db.session.add(assignment)
    create_audit("application.reviewer_assigned", "application", application.id, g.user, {"reviewer_id": reviewer.id})
    db.session.commit()
    return jsonify({"assignment_id": assignment.id}), 201


@api.post("/admin/applications/<application_id>/scorecards")
@require_roles(*REVIEWER_ROLES)
def submit_scorecard(application_id: str):
    application = db.session.get(Application, application_id)
    data = payload()
    if not application or not can_view_application(g.user, application):
        return json_error("Application not found", 404)
    if not data.get("recommendation") or not data.get("comment"):
        return json_error("recommendation and comment are required")
    scorecard = ReviewScorecard(
        application_id=application.id,
        reviewer_id=g.user.id,
        scores=data.get("scores") or {},
        recommendation=data["recommendation"],
        comment=data["comment"],
    )
    db.session.add(scorecard)
    create_audit("application.scorecard_submitted", "application", application.id, g.user)
    db.session.commit()
    return jsonify({"scorecard_id": scorecard.id}), 201


@api.post("/admin/interviews")
@require_roles(*ADMIN_ROLES)
def schedule_interview():
    data = payload()
    application = db.session.get(Application, data.get("application_id"))
    if not application:
        return json_error("Application not found", 404)
    starts_at = parse_datetime(data.get("starts_at"))
    ends_at = parse_datetime(data.get("ends_at"))
    if not starts_at or not ends_at:
        return json_error("starts_at and ends_at are required")
    interview = Interview(
        application_id=application.id,
        candidate_id=application.candidate_id,
        interviewer_id=data.get("interviewer_id"),
        interview_type=data.get("interview_type") or "Technical Interview",
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=data.get("timezone") or "Asia/Kolkata",
        meeting_mode=data.get("meeting_mode") or "Video",
        meeting_link=data.get("meeting_link"),
        physical_location=data.get("physical_location"),
        candidate_instructions=data.get("candidate_instructions"),
        internal_instructions=data.get("internal_instructions"),
        status=data.get("status") or "Invitation Sent",
    )
    db.session.add(interview)
    update_application_status(application, "Interview Scheduled", g.user, "Interview scheduled")
    create_notification(
        application.candidate_id,
        "Interview scheduled",
        f"Your interview for {application.job.title} has been scheduled.",
        "interview_invitation",
        application.id,
    )
    db.session.commit()
    return jsonify({"interview": interview_to_dict(interview)}), 201


@api.get("/admin/interviews")
@require_roles(*REVIEWER_ROLES)
def list_interviews():
    query = Interview.query.order_by(Interview.starts_at.asc())
    return jsonify({"interviews": [interview_to_dict(item) for item in query.all()]})


@api.get("/admin/candidates")
@require_roles(*ADMIN_ROLES)
def admin_candidates():
    query = User.query.filter_by(role="candidate").order_by(User.created_at.desc())
    return jsonify({"candidates": [user_to_dict(user) for user in query.all()]})


@api.get("/admin/users")
@require_roles("super_admin")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [user_to_dict(user) for user in users]})


@api.post("/admin/users")
@require_roles("super_admin")
def create_admin_user():
    data = payload()
    role = data.get("role")
    if role not in REVIEWER_ROLES:
        return json_error("Invalid admin/reviewer role")
    if not password_is_valid(data.get("password", "")):
        return json_error("Password must be at least 8 characters and include a letter and a number")
    user = User(
        email=normalize_email(data.get("email", "")),
        password_hash=hash_password(data["password"]),
        full_name=data.get("full_name") or data.get("email"),
        role=role,
        is_verified=True,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("User already exists", 409)
    return jsonify({"user": user_to_dict(user)}), 201


@api.get("/admin/templates")
@require_roles(*ADMIN_ROLES)
def list_templates():
    templates = EmailTemplate.query.order_by(EmailTemplate.key.asc()).all()
    return jsonify(
        {
            "templates": [
                {
                    "id": item.id,
                    "key": item.key,
                    "subject": item.subject,
                    "html_body": item.html_body,
                    "text_body": item.text_body,
                    "version": item.version,
                    "is_active": item.is_active,
                }
                for item in templates
            ]
        }
    )


@api.put("/admin/templates/<key>")
@require_roles(*ADMIN_ROLES)
def upsert_template(key: str):
    data = payload()
    template = EmailTemplate.query.filter_by(key=key).first() or EmailTemplate(key=key)
    template.subject = data.get("subject") or template.subject or key.replace("_", " ").title()
    template.html_body = data.get("html_body") or template.html_body or ""
    template.text_body = data.get("text_body") or template.text_body or ""
    template.version = (template.version or 0) + 1
    template.is_active = data.get("is_active", True)
    db.session.add(template)
    create_audit("email_template.upserted", "email_template", template.id, g.user, {"key": key})
    db.session.commit()
    return jsonify({"template_id": template.id})


@api.get("/admin/audit-logs")
@require_roles("super_admin")
def audit_logs():
    from .models import AuditLog

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return jsonify(
        {
            "audit_logs": [
                {
                    "id": log.id,
                    "actor_id": log.actor_id,
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "details": log.details,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        }
    )


@api.get("/candidate/interviews/<interview_id>/ics")
@require_auth
def interview_ics(interview_id: str):
    interview = db.session.get(Interview, interview_id)
    if not interview:
        return json_error("Interview not found", 404)
    application = db.session.get(Application, interview.application_id)
    if not application or not can_view_application(g.user, application):
        return json_error("Interview not found", 404)
    start = interview.starts_at.strftime("%Y%m%dT%H%M%SZ")
    end = interview.ends_at.strftime("%Y%m%dT%H%M%SZ")
    body = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Pravaron Careers//Interview//EN",
            "BEGIN:VEVENT",
            f"UID:{interview.id}@careers.pravarontechnologies.com",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:Pravaron Careers - {interview.interview_type}",
            f"DESCRIPTION:{interview.candidate_instructions or ''}",
            f"LOCATION:{interview.meeting_link or interview.physical_location or ''}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    return Response(body, mimetype="text/calendar", headers={"Content-Disposition": "attachment; filename=pravaron-interview.ics"})
