from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


json_type = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="candidate", index=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))

    profile = db.relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class CandidateProfile(db.Model, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    phone = db.Column(db.String(40))
    current_city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    country = db.Column(db.String(120), default="India")
    preferred_work_location = db.Column(db.String(160))
    current_role = db.Column(db.String(160))
    total_experience_years = db.Column(db.Float)
    current_company = db.Column(db.String(160))
    notice_period = db.Column(db.String(120))
    current_compensation = db.Column(db.String(80))
    expected_compensation = db.Column(db.String(80))
    skills = db.Column(json_type, default=list, nullable=False)
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    personal_website_url = db.Column(db.String(500))
    extra_metadata = db.Column("profile_metadata", json_type, default=dict, nullable=False)

    user = db.relationship("User", back_populates="profile")


class Resume(db.Model, TimestampMixin):
    __tablename__ = "resumes"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(700), nullable=False)
    content_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer, nullable=False)
    checksum_sha256 = db.Column(db.String(64), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    scan_status = db.Column(db.String(40), nullable=False, default="pending")


class Job(db.Model, TimestampMixin):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    public_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    department = db.Column(db.String(120))
    employment_type = db.Column(db.String(80), nullable=False, default="Full-time")
    experience_level = db.Column(db.String(80))
    openings = db.Column(db.Integer, default=1)
    location = db.Column(db.String(160))
    workplace_model = db.Column(db.String(80), default="Hybrid")
    salary_display = db.Column(db.String(40), default="hidden")
    min_salary = db.Column(db.Integer)
    max_salary = db.Column(db.Integer)
    currency = db.Column(db.String(10), default="INR")
    role_summary = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text)
    required_skills = db.Column(json_type, default=list, nullable=False)
    preferred_skills = db.Column(json_type, default=list, nullable=False)
    education_preference = db.Column(db.String(255))
    experience_requirement = db.Column(db.String(255))
    application_questions = db.Column(json_type, default=list, nullable=False)
    selection_process = db.Column(db.Text)
    application_deadline = db.Column(db.DateTime(timezone=True))
    publish_at = db.Column(db.DateTime(timezone=True))
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    status = db.Column(db.String(40), nullable=False, default="draft", index=True)
    source_metadata = db.Column(json_type, default=dict, nullable=False)


class Application(db.Model, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_application"),)

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.String(36), db.ForeignKey("resumes.id"))
    cover_message = db.Column(db.Text)
    answers = db.Column(json_type, default=dict, nullable=False)
    declarations = db.Column(json_type, default=dict, nullable=False)
    source = db.Column(db.String(120))
    candidate_status = db.Column(db.String(80), nullable=False, default="Application Submitted", index=True)
    internal_status = db.Column(db.String(80), nullable=False, default="New", index=True)
    rejection_reason = db.Column(db.String(120))
    withdrawn_at = db.Column(db.DateTime(timezone=True))
    withdrawal_reason = db.Column(db.Text)

    candidate = db.relationship("User", foreign_keys=[candidate_id])
    job = db.relationship("Job")
    resume = db.relationship("Resume")


class ApplicationEvent(db.Model):
    __tablename__ = "application_events"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    event_type = db.Column(db.String(80), nullable=False)
    previous_status = db.Column(db.String(80))
    new_status = db.Column(db.String(80))
    note = db.Column(db.Text)
    visible_to_candidate = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class InternalNote(db.Model, TimestampMixin):
    __tablename__ = "internal_notes"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    edited_at = db.Column(db.DateTime(timezone=True))


class ReviewerAssignment(db.Model, TimestampMixin):
    __tablename__ = "reviewer_assignments"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    reviewer_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id", ondelete="CASCADE"))
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"))
    assigned_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)


class ReviewScorecard(db.Model, TimestampMixin):
    __tablename__ = "review_scorecards"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    scores = db.Column(json_type, default=dict, nullable=False)
    recommendation = db.Column(db.String(80), nullable=False)
    comment = db.Column(db.Text, nullable=False)


class Interview(db.Model, TimestampMixin):
    __tablename__ = "interviews"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    interviewer_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    interview_type = db.Column(db.String(80), nullable=False)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    timezone = db.Column(db.String(80), default="Asia/Kolkata")
    meeting_mode = db.Column(db.String(80), default="Video")
    meeting_link = db.Column(db.String(700))
    physical_location = db.Column(db.String(500))
    candidate_instructions = db.Column(db.Text)
    internal_instructions = db.Column(db.Text)
    status = db.Column(db.String(80), nullable=False, default="Draft")


class Notification(db.Model, TimestampMixin):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    recipient_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"))
    notification_type = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(40), nullable=False, default="in_app")
    delivery_status = db.Column(db.String(40), nullable=False, default="pending")
    sent_at = db.Column(db.DateTime(timezone=True))
    read_at = db.Column(db.DateTime(timezone=True))
    failure_reason = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0, nullable=False)


class EmailTemplate(db.Model, TimestampMixin):
    __tablename__ = "email_templates"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    key = db.Column(db.String(100), unique=True, nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    html_body = db.Column(db.Text, nullable=False)
    text_body = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    actor_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(36))
    ip_address = db.Column(db.String(80))
    user_agent = db.Column(db.String(500))
    details = db.Column(json_type, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
