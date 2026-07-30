from __future__ import annotations

import imaplib
import re
import uuid
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape

from sqlalchemy.exc import IntegrityError

from .applicant_details import create_or_update_applicant_detail
from .auth import hash_password, normalize_email
from .extensions import db
from .models import Application, ApplicationEvent, CandidateProfile, InternalNote, Job, User
from .services import create_audit, save_resume_bytes, slugify

APPLICATION_KEYWORDS = {
    "application",
    "applying",
    "apply",
    "applicant",
    "candidate",
    "resume",
    "cv",
    "curriculum vitae",
    "job",
    "opening",
    "vacancy",
    "internship",
    "developer",
    "engineer",
    "hiring",
    "linkedin",
}

IGNORED_SENDER_TOKENS = {"mailer-daemon", "postmaster", "no-reply", "noreply", "messages-noreply", "welcome", "info", "support", "notifications"}
RESUME_EXTENSIONS = {"pdf", "doc", "docx"}
GENERAL_JOB_CODE = "PRV-MAIL-GEN"
GENERAL_JOB_SLUG = "general-email-application"


@dataclass
class MailAttachment:
    filename: str
    content_type: str | None
    payload: bytes


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _plain_body(message: EmailMessage) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in message.walk():
        if part.is_attachment():
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            plain_parts.append(str(content))
        else:
            html_parts.append(str(content))
    if plain_parts:
        return "\n\n".join(plain_parts).strip()
    html = "\n\n".join(html_parts)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p\s*>", "\n\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", unescape(html)).strip()


def _attachment_rank(attachment: MailAttachment) -> tuple[int, str]:
    name = attachment.filename.lower()
    if "cover" in name or "letter" in name:
        return (3, name)
    if "resume" in name or "cv" in name or "curriculum" in name:
        return (0, name)
    if name.endswith(".pdf"):
        return (1, name)
    return (2, name)

def _attachments(message: EmailMessage) -> list[MailAttachment]:
    items: list[MailAttachment] = []
    for part in message.iter_attachments():
        filename = _decode_header(part.get_filename())
        if not filename or "." not in filename:
            continue
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in RESUME_EXTENSIONS:
            continue
        payload = part.get_payload(decode=True) or b""
        if not payload:
            continue
        items.append(MailAttachment(filename=filename, content_type=part.get_content_type(), payload=payload))
    return items


def _is_application_related(subject: str, body: str, from_email: str, attachments: list[MailAttachment]) -> bool:
    local_sender = from_email.split("@", 1)[0].lower()
    if local_sender in IGNORED_SENDER_TOKENS:
        return False
    text = f"{subject}\n{body}".lower()
    if not attachments:
        return False
    if any(keyword in text for keyword in APPLICATION_KEYWORDS):
        return True
    return any(token in text for token in {"role", "position", "opportunity", "pravaron"})


def _existing_message_ids() -> set[str]:
    message_ids: set[str] = set()
    for application in Application.query.all():
        answers = application.answers or {}
        if not isinstance(answers, dict):
            continue
        email_info = answers.get("email")
        if isinstance(email_info, dict) and email_info.get("message_id"):
            message_ids.add(str(email_info["message_id"]))
        for imported_id in answers.get("email_import_message_ids") or []:
            message_ids.add(str(imported_id))
    return message_ids


def _candidate_name(from_name: str, email_address: str) -> str:
    if from_name:
        return from_name[:160]
    local = email_address.split("@", 1)[0]
    cleaned = re.sub(r"[._-]+", " ", local).strip().title()
    return cleaned or email_address


def _get_or_create_candidate(email_address: str, full_name: str) -> User:
    user = User.query.filter_by(email=email_address).first()
    if user:
        if not user.full_name and full_name:
            user.full_name = full_name
        return user
    try:
        with db.session.begin_nested():
            user = User(
                email=email_address,
                password_hash=hash_password(uuid.uuid4().hex + "A1"),
                full_name=full_name,
                role="candidate",
                is_verified=True,
            )
            user.profile = CandidateProfile(extra_metadata={"source": "email_import"})
            db.session.add(user)
            db.session.flush()
            create_audit("mail_import.candidate_created", "user", user.id, user, {"email": email_address})
        return user
    except IntegrityError:
        user = User.query.filter_by(email=email_address).first()
        if not user:
            raise
        if not user.full_name and full_name:
            user.full_name = full_name
        return user


def _general_email_job(actor: User) -> Job:
    job = Job.query.filter_by(public_code=GENERAL_JOB_CODE).first()
    if job:
        return job
    job = Job(
        public_code=GENERAL_JOB_CODE,
        title="General Email Application",
        slug=GENERAL_JOB_SLUG,
        department="People Operations",
        employment_type="Full-time",
        openings=1,
        workplace_model="Hybrid",
        salary_display="hidden",
        role_summary="Applications imported from careers mailbox where no specific job could be matched.",
        required_skills=[],
        preferred_skills=[],
        application_questions=[],
        source_metadata={"private_mail_import": True},
        status="draft",
        created_by_id=actor.id,
    )
    db.session.add(job)
    db.session.flush()
    create_audit("mail_import.general_job_created", "job", job.id, actor)
    return job


def _role_score(job: Job, text: str) -> int:
    title = (job.title or "").lower()
    family = ((job.source_metadata or {}).get("role_family") or "").lower()
    score = 0
    if job.public_code and job.public_code.lower() in text:
        score += 100
    if job.slug and job.slug.lower() in text:
        score += 80
    if title and title in text:
        score += 80
    if family in {"full_stack", "frontend"}:
        if any(token in text for token in ["full stack", "full-stack", "fullstack", "mern", "software developer", "react", "next.js", "node", "frontend", "backend"]):
            score += 40 if family == "full_stack" else 25
    if family == "frontend" and any(token in text for token in ["frontend", "front-end", "react", "next.js", "ui developer"]):
        score += 50
    if family in {"ai_ml_backend", "ai_ml"} and any(token in text for token in ["ai/ml", "ai ml", "machine learning", "ml", "ai engineer", "backend", "python", "rag", "llm", "nlp"]):
        score += 50 if family == "ai_ml_backend" else 42
    if family == "ui_ux" and any(token in text for token in ["ui/ux", "ux", "ui designer", "figma", "product design", "designer"]):
        score += 60
    if "intern" in text and job.employment_type == "Internship":
        score += 20
    if any(token in text for token in ["1 year", "2 year", "experienced", "full-time", "full time"]) and job.employment_type == "Full-time":
        score += 12
    return score


def _match_job(subject: str, body: str, actor: User) -> Job:
    text = f"{subject}\n{body}".lower()
    jobs = [job for job in Job.query.order_by(Job.status.desc(), Job.created_at.desc()).all() if job.public_code != GENERAL_JOB_CODE]
    scored = sorted(((_role_score(job, text), job) for job in jobs), key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= 35:
        return scored[0][1]
    return _general_email_job(actor)


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def _message_id(message: EmailMessage, fallback_uid: bytes) -> str:
    raw = _decode_header(message.get("Message-ID"))
    return raw or f"imap:{fallback_uid.decode(errors='ignore')}"


def _import_message(message: EmailMessage, uid: bytes, actor: User, seen_message_ids: set[str]) -> tuple[str, str | None]:
    message_id = _message_id(message, uid)
    if message_id in seen_message_ids:
        return "skipped_duplicate", None

    subject = _decode_header(message.get("Subject")) or "No subject"
    from_name, from_email = parseaddr(_decode_header(message.get("From")))
    from_email = normalize_email(from_email)
    if not from_email:
        return "skipped_unreadable", None

    body = _plain_body(message)
    attachments = _attachments(message)
    if not _is_application_related(subject, body, from_email, attachments):
        return "skipped_unrelated", None

    candidate = _get_or_create_candidate(from_email, _candidate_name(from_name, from_email))
    job = _match_job(subject, body, actor)
    existing = Application.query.filter_by(candidate_id=candidate.id, job_id=job.id).first()
    if existing:
        answers = dict(existing.answers or {})
        imported_ids = {str(item) for item in answers.get("email_import_message_ids") or []}
        if message_id in imported_ids:
            seen_message_ids.add(message_id)
            return "skipped_duplicate", existing.id
        imported_ids.add(message_id)
        answers["email_import_message_ids"] = sorted(imported_ids)
        existing.answers = answers
        note_body = f"Additional application email received: {subject}\n\nMessage-ID: {message_id}"
        db.session.add(InternalNote(application_id=existing.id, author_id=actor.id, body=note_body[:4000]))
        db.session.add(
            ApplicationEvent(
                application_id=existing.id,
                actor_id=actor.id,
                event_type="email_received",
                note=f"Additional email imported from {from_email}",
                visible_to_candidate=False,
            )
        )
        if existing.resume_id:
            create_or_update_applicant_detail(existing)
        seen_message_ids.add(message_id)
        return "skipped_existing_application", existing.id

    saved_attachments = []
    primary_resume_id = None
    for attachment in sorted(attachments, key=_attachment_rank):
        try:
            resume = save_resume_bytes(candidate, attachment.filename, attachment.payload, attachment.content_type)
        except ValueError:
            continue
        saved_attachments.append(
            {
                "resume_id": resume.id,
                "filename": resume.original_filename,
                "content_type": resume.content_type,
                "size_bytes": resume.size_bytes,
            }
        )
        primary_resume_id = primary_resume_id or resume.id

    sent_at = _parse_date(message.get("Date"))
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_id=primary_resume_id,
        cover_message=body[:12000],
        answers={
            "email": {
                "message_id": message_id,
                "subject": subject,
                "from_name": from_name,
                "from_email": from_email,
                "sent_at": sent_at.isoformat() if sent_at else None,
                "imap_uid": uid.decode(errors="ignore"),
                "attachments": saved_attachments,
            },
            "email_import_message_ids": [message_id],
        },
        declarations={"accuracy": False, "privacy": False, "imported_from_email": True},
        source="email",
    )
    db.session.add(application)
    db.session.flush()
    db.session.add(
        ApplicationEvent(
            application_id=application.id,
            actor_id=actor.id,
            event_type="email_imported",
            new_status=application.internal_status,
            note=f"Imported from mailbox email: {subject}",
            visible_to_candidate=False,
        )
    )
    create_or_update_applicant_detail(application)
    create_audit("mail_import.application_created", "application", application.id, actor, {"message_id": message_id})
    seen_message_ids.add(message_id)
    return "imported", application.id


def sync_careers_mailbox(actor: User, limit: int | None = None) -> dict:
    from flask import current_app

    password = current_app.config["CAREERS_MAIL_APP_PASSWORD"]
    if not password:
        raise ValueError("CAREERS_MAIL_APP_PASSWORD is not configured")

    host = current_app.config["CAREERS_MAIL_IMAP_HOST"]
    port = current_app.config["CAREERS_MAIL_IMAP_PORT"]
    username = current_app.config["CAREERS_MAIL_USERNAME"]
    mailbox = current_app.config["CAREERS_MAIL_MAILBOX"]
    fetch_limit = min(limit or current_app.config["CAREERS_MAIL_FETCH_LIMIT"], 1000)

    summary = {
        "mailbox": mailbox,
        "checked": 0,
        "imported": 0,
        "skipped_duplicate": 0,
        "skipped_existing_application": 0,
        "skipped_unrelated": 0,
        "skipped_unreadable": 0,
        "errors": [],
        "application_ids": [],
    }

    seen_message_ids = _existing_message_ids()
    with imaplib.IMAP4_SSL(host, port) as client:
        client.login(username, password)
        client.select(mailbox)
        status, payload = client.search(None, "ALL")
        if status != "OK" or not payload:
            return summary
        uids = payload[0].split()[-fetch_limit:]
        for uid in reversed(uids):
            summary["checked"] += 1
            status, message_data = client.fetch(uid, "(RFC822)")
            if status != "OK" or not message_data:
                summary["skipped_unreadable"] += 1
                continue
            raw = next((item[1] for item in message_data if isinstance(item, tuple)), None)
            if not raw:
                summary["skipped_unreadable"] += 1
                continue
            try:
                message = message_from_bytes(raw, policy=default)
                result, application_id = _import_message(message, uid, actor, seen_message_ids)
                summary[result] += 1
                if application_id and result in {"imported", "skipped_existing_application"}:
                    summary["application_ids"].append(application_id)
                db.session.commit()
            except IntegrityError as exc:
                db.session.rollback()
                summary["errors"].append(str(exc.orig)[:300])
            except Exception as exc:
                db.session.rollback()
                summary["errors"].append(str(exc)[:300])
    return summary
