from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .extensions import db
from .models import (
    Application,
    ApplicationEvent,
    AuditLog,
    Job,
    Notification,
    Resume,
    User,
    utcnow,
    uuid_str,
)

STATUS_MAP = {
    "New": "Application Submitted",
    "Assigned for Review": "Under Initial Review",
    "HR Review": "Under Initial Review",
    "Technical Review": "Under Initial Review",
    "Manager Review": "Final Review",
    "Shortlisted": "Shortlisted",
    "Interview Scheduled": "Interview Scheduled",
    "Interview Completed": "Interview Completed",
    "Decision Pending": "Final Review",
    "Offer Sent": "Offer Released",
    "Hired": "Hired",
    "Rejected": "Not Selected",
    "Withdrawn": "Application Withdrawn",
    "On Hold": "Position On Hold",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or uuid_str()


def create_audit(action: str, entity_type: str, entity_id: str | None = None, actor: User | None = None, details=None):
    db.session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
            details=details or {},
        )
    )


def create_notification(
    recipient_id: str,
    subject: str,
    message: str,
    notification_type: str,
    application_id: str | None = None,
    channel: str = "in_app",
):
    notification = Notification(
        recipient_id=recipient_id,
        application_id=application_id,
        subject=subject,
        message=message,
        notification_type=notification_type,
        channel=channel,
        delivery_status="sent" if channel == "in_app" else "queued",
        sent_at=utcnow() if channel == "in_app" else None,
    )
    db.session.add(notification)
    return notification


def next_public_code() -> str:
    count = db.session.query(Job).count() + 1
    return f"PRV-CAR-{count:04d}"


def parse_datetime(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def job_accepts_applications(job: Job) -> bool:
    if job.status != "published":
        return False
    if job.application_deadline and job.application_deadline < datetime.now(timezone.utc):
        return False
    if job.publish_at and job.publish_at > datetime.now(timezone.utc):
        return False
    return True


def update_application_status(application: Application, internal_status: str, actor: User, note: str | None = None, rejection_reason: str | None = None):
    previous_candidate = application.candidate_status
    previous_internal = application.internal_status
    candidate_status = STATUS_MAP.get(internal_status, internal_status)
    application.internal_status = internal_status
    application.candidate_status = candidate_status
    application.rejection_reason = rejection_reason
    event = ApplicationEvent(
        application_id=application.id,
        actor_id=actor.id,
        event_type="status_changed",
        previous_status=previous_internal,
        new_status=internal_status,
        note=note,
        visible_to_candidate=previous_candidate != candidate_status,
    )
    db.session.add(event)
    if previous_candidate != candidate_status:
        create_notification(
            recipient_id=application.candidate_id,
            application_id=application.id,
            notification_type="application_status_changed",
            subject=f"Application status updated: {candidate_status}",
            message=f"Your application for {application.job.title} is now {candidate_status}.",
        )
    create_audit("application.status_changed", "application", application.id, actor, {"from": previous_internal, "to": internal_status})


def save_resume_file(user: User, upload: FileStorage) -> Resume:
    filename = secure_filename(upload.filename or "")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in current_app.config["ALLOWED_RESUME_EXTENSIONS"]:
        raise ValueError("Resume must be a PDF, DOC, or DOCX file")

    raw = upload.read()
    if not raw:
        raise ValueError("Resume file is empty")
    checksum = hashlib.sha256(raw).hexdigest()
    version = db.session.query(Resume).filter_by(user_id=user.id).count() + 1
    folder = Path(current_app.root_path).parent / current_app.config["UPLOAD_FOLDER"] / user.id
    folder.mkdir(parents=True, exist_ok=True)
    storage_name = f"resume-v{version}-{checksum[:12]}.{ext}"
    storage_path = folder / storage_name
    storage_path.write_bytes(raw)

    resume = Resume(
        user_id=user.id,
        original_filename=filename,
        storage_path=os.fspath(storage_path),
        content_type=upload.mimetype,
        size_bytes=len(raw),
        checksum_sha256=checksum,
        version=version,
        scan_status="pending",
    )
    db.session.add(resume)
    create_audit("resume.uploaded", "resume", resume.id, user, {"filename": filename, "size_bytes": len(raw)})
    return resume

