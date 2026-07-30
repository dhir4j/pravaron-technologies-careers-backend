from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def duration_seconds(start_dt: datetime | None, end_dt: datetime | None = None) -> int:
    if not start_dt:
        return 0
    s = ensure_utc(start_dt)
    e = ensure_utc(end_dt or utcnow())
    if s and e:
        return max(0, int((e - s).total_seconds()))
    return 0


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
    education_preference = db.Column(db.Text)
    experience_requirement = db.Column(db.Text)
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
    applicant_detail = db.relationship("ApplicantDetail", back_populates="application", uselist=False, cascade="all, delete-orphan")
    candidate_analysis = db.relationship("CandidateAnalysis", back_populates="application", uselist=False, cascade="all, delete-orphan")


class ApplicantDetail(db.Model, TimestampMixin):
    __tablename__ = "applicant_details"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.String(36), db.ForeignKey("resumes.id", ondelete="SET NULL"), index=True)
    source = db.Column(db.String(120))
    full_name = db.Column(db.String(160))
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(80))
    current_city = db.Column(db.String(160))
    current_role = db.Column(db.String(180))
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    email_subject = db.Column(db.String(500))
    email_message_id = db.Column(db.String(500), index=True)
    email_sent_at = db.Column(db.String(80))
    resume_filename = db.Column(db.String(255))
    resume_content_type = db.Column(db.String(120))
    resume_size_bytes = db.Column(db.Integer)
    resume_text = db.Column(db.Text)
    parsed_fields = db.Column(json_type, default=dict, nullable=False)
    extraction_status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    extraction_error = db.Column(db.Text)

    application = db.relationship("Application", back_populates="applicant_detail")
    candidate = db.relationship("User", foreign_keys=[candidate_id])
    resume = db.relationship("Resume", foreign_keys=[resume_id])


class CandidateAnalysis(db.Model, TimestampMixin):
    __tablename__ = "candidate_analyses"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    applicant_detail_id = db.Column(db.String(36), db.ForeignKey("applicant_details.id", ondelete="CASCADE"), index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.String(36), db.ForeignKey("resumes.id", ondelete="SET NULL"), index=True)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    model = db.Column(db.String(120), nullable=False)
    input_hash = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    suitability_score = db.Column(db.Integer)
    confidence_score = db.Column(db.Integer)
    recommendation = db.Column(db.String(80))
    graduation_year = db.Column(db.Integer)
    recommended_track = db.Column(db.String(80))
    location_priority = db.Column(db.String(80))
    detected_location = db.Column(db.String(160))
    job_family = db.Column(db.String(120))
    headline = db.Column(db.String(255))
    summary = db.Column(db.Text)
    experience_summary = db.Column(db.Text)
    education_summary = db.Column(db.Text)
    projects_summary = db.Column(db.Text)
    skills = db.Column(json_type, default=list, nullable=False)
    languages = db.Column(json_type, default=list, nullable=False)
    frameworks = db.Column(json_type, default=list, nullable=False)
    tools = db.Column(json_type, default=list, nullable=False)
    strengths = db.Column(json_type, default=list, nullable=False)
    concerns = db.Column(json_type, default=list, nullable=False)
    project_highlights = db.Column(json_type, default=list, nullable=False)
    job_fit = db.Column(json_type, default=dict, nullable=False)
    interview_questions = db.Column(json_type, default=list, nullable=False)
    raw_analysis = db.Column(json_type, default=dict, nullable=False)
    usage = db.Column(json_type, default=dict, nullable=False)
    error = db.Column(db.Text)
    analyzed_at = db.Column(db.DateTime(timezone=True))

    application = db.relationship("Application", back_populates="candidate_analysis")
    applicant_detail = db.relationship("ApplicantDetail")
    candidate = db.relationship("User", foreign_keys=[candidate_id])
    resume = db.relationship("Resume", foreign_keys=[resume_id])
    job = db.relationship("Job", foreign_keys=[job_id])



class ApplicationGroup(db.Model, TimestampMixin):
    __tablename__ = "application_groups"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    name = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text)
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(40), nullable=False, default="active", index=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    members = db.relationship("ApplicationGroupMember", back_populates="group", cascade="all, delete-orphan")


class ApplicationGroupMember(db.Model, TimestampMixin):
    __tablename__ = "application_group_members"
    __table_args__ = (UniqueConstraint("group_id", "application_id", name="uq_group_application_member"),)

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    group_id = db.Column(db.String(36), db.ForeignKey("application_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    group = db.relationship("ApplicationGroup", back_populates="members")
    application = db.relationship("Application", foreign_keys=[application_id])
    added_by = db.relationship("User", foreign_keys=[added_by_id])


class ApplicationGroupEmail(db.Model, TimestampMixin):
    __tablename__ = "application_group_emails"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    group_id = db.Column(db.String(36), db.ForeignKey("application_groups.id", ondelete="SET NULL"), index=True)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="SET NULL"), index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    sent_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    to_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    html_body = db.Column(db.Text, nullable=False)
    text_body = db.Column(db.Text)
    purpose = db.Column(db.String(120))
    status_to_apply = db.Column(db.String(80))
    delivery_status = db.Column(db.String(40), nullable=False, default="queued")
    failure_reason = db.Column(db.Text)
    sent_at = db.Column(db.DateTime(timezone=True))

    group = db.relationship("ApplicationGroup", foreign_keys=[group_id])
    application = db.relationship("Application", foreign_keys=[application_id])
    candidate = db.relationship("User", foreign_keys=[candidate_id])
    sent_by = db.relationship("User", foreign_keys=[sent_by_id])

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



class Education(db.Model, TimestampMixin):
    __tablename__ = "education"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    institution = db.Column(db.String(200), nullable=False)
    degree = db.Column(db.String(150), nullable=False)
    field_of_study = db.Column(db.String(150))
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    is_current = db.Column(db.Boolean, default=False, nullable=False)
    grade = db.Column(db.String(50))
    description = db.Column(db.Text)


class Employment(db.Model, TimestampMixin):
    __tablename__ = "employment"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company = db.Column(db.String(200), nullable=False)
    job_title = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False, nullable=False)
    responsibilities = db.Column(db.Text)
    achievements = db.Column(db.Text)
    location = db.Column(db.String(150))


# ─────────────────────────────────────────────
# Phase 1 completion models
# ─────────────────────────────────────────────

class InterviewFeedback(db.Model, TimestampMixin):
    __tablename__ = "interview_feedback"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    interview_id = db.Column(db.String(36), db.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    technical_score = db.Column(db.Integer)
    communication_score = db.Column(db.Integer)
    problem_solving_score = db.Column(db.Integer)
    cultural_fit_score = db.Column(db.Integer)
    overall_recommendation = db.Column(db.String(40))  # Hire / Consider / Reject
    strengths = db.Column(db.Text)
    concerns = db.Column(db.Text)
    notes = db.Column(db.Text)

    interview = db.relationship("Interview", foreign_keys=[interview_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])


class OfferLetter(db.Model, TimestampMixin):
    __tablename__ = "offer_letters"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    role_title = db.Column(db.String(180), nullable=False)
    department = db.Column(db.String(120))
    joining_date = db.Column(db.Date)
    compensation_details = db.Column(db.Text)
    additional_terms = db.Column(db.Text)
    status = db.Column(db.String(40), nullable=False, default="draft")  # draft / sent / accepted / declined
    sent_at = db.Column(db.DateTime(timezone=True))
    responded_at = db.Column(db.DateTime(timezone=True))

    application = db.relationship("Application", foreign_keys=[application_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


# ─────────────────────────────────────────────
# Phase 2 models
# ─────────────────────────────────────────────

class InconsistencyFlag(db.Model, TimestampMixin):
    __tablename__ = "inconsistency_flags"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    flags = db.Column(json_type, default=list, nullable=False)  # [{field, expected, found, severity}]
    reviewed = db.Column(db.Boolean, default=False, nullable=False)
    reviewer_note = db.Column(db.Text)
    detected_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    application = db.relationship("Application", foreign_keys=[application_id])


# ─────────────────────────────────────────────
# Phase 3 — Online Assessment Platform
# ─────────────────────────────────────────────

class Assessment(db.Model, TimestampMixin):
    __tablename__ = "assessments"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assessment_type = db.Column(db.String(80), nullable=False, default="aptitude")  # aptitude | technical | coding | assignment
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    time_limit_minutes = db.Column(db.Integer, nullable=False, default=60)
    max_attempts = db.Column(db.Integer, nullable=False, default=1)
    pass_score = db.Column(db.Integer, nullable=False, default=60)  # percentage
    randomize_questions = db.Column(db.Boolean, default=False, nullable=False)
    instructions = db.Column(db.Text)
    status = db.Column(db.String(40), nullable=False, default="draft", index=True)  # draft | active | archived
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    questions = db.relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentQuestion.order")
    attempts = db.relationship("AssessmentAttempt", back_populates="assessment", cascade="all, delete-orphan")
    job = db.relationship("Job", foreign_keys=[job_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class AssessmentQuestion(db.Model, TimestampMixin):
    __tablename__ = "assessment_questions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    assessment_id = db.Column(db.String(36), db.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_type = db.Column(db.String(40), nullable=False)  # mcq | multi_select | text | code | file_upload
    content = db.Column(db.Text, nullable=False)
    options = db.Column(json_type, default=list, nullable=False)  # for mcq/multi_select
    correct_answer = db.Column(json_type)  # for auto-graded types
    explanation = db.Column(db.Text)
    marks = db.Column(db.Integer, nullable=False, default=1)
    order = db.Column(db.Integer, nullable=False, default=0)
    time_limit_seconds = db.Column(db.Integer)
    code_template = db.Column(db.Text)  # starter code for coding questions
    code_language = db.Column(db.String(40))  # python | javascript | java | cpp | etc.

    assessment = db.relationship("Assessment", back_populates="questions")
    responses = db.relationship("AssessmentResponse", back_populates="question", cascade="all, delete-orphan")


class AssessmentAttempt(db.Model, TimestampMixin):
    __tablename__ = "assessment_attempts"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    assessment_id = db.Column(db.String(36), db.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="not_started", index=True)  # not_started | in_progress | submitted | timed_out | graded
    started_at = db.Column(db.DateTime(timezone=True))
    submitted_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    auto_score = db.Column(db.Float, default=0)
    max_auto_score = db.Column(db.Float, default=0)
    manual_score = db.Column(db.Float)
    final_score = db.Column(db.Float)
    percentage = db.Column(db.Float)
    is_passed = db.Column(db.Boolean)
    graded_by_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    graded_at = db.Column(db.DateTime(timezone=True))
    grader_notes = db.Column(db.Text)

    assessment = db.relationship("Assessment", back_populates="attempts")
    application = db.relationship("Application", foreign_keys=[application_id])
    candidate = db.relationship("User", foreign_keys=[candidate_id])
    graded_by = db.relationship("User", foreign_keys=[graded_by_id])
    responses = db.relationship("AssessmentResponse", back_populates="attempt", cascade="all, delete-orphan")
    proctoring_session = db.relationship("ProctoringSession", back_populates="attempt", uselist=False, cascade="all, delete-orphan")


class AssessmentResponse(db.Model, TimestampMixin):
    __tablename__ = "assessment_responses"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_response"),)

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    attempt_id = db.Column(db.String(36), db.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    response = db.Column(json_type)  # answer content (text, selected options, code string)
    is_correct = db.Column(db.Boolean)
    auto_marks = db.Column(db.Float, default=0)
    time_taken_seconds = db.Column(db.Integer)
    manual_marks = db.Column(db.Float)
    reviewer_comment = db.Column(db.Text)
    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"))

    attempt = db.relationship("AssessmentAttempt", back_populates="responses")
    question = db.relationship("AssessmentQuestion", back_populates="responses")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


# ─────────────────────────────────────────────
# Phase 4 — Proctoring
# ─────────────────────────────────────────────

class ProctoringSession(db.Model, TimestampMixin):
    __tablename__ = "proctoring_sessions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    attempt_id = db.Column(db.String(36), db.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    fullscreen_exits = db.Column(db.Integer, default=0, nullable=False)
    tab_switches = db.Column(db.Integer, default=0, nullable=False)
    focus_losses = db.Column(db.Integer, default=0, nullable=False)
    copy_paste_events = db.Column(db.Integer, default=0, nullable=False)
    face_not_detected_count = db.Column(db.Integer, default=0, nullable=False)
    multiple_faces_count = db.Column(db.Integer, default=0, nullable=False)
    mobile_detected_count = db.Column(db.Integer, default=0, nullable=False)
    suspicious_total = db.Column(db.Integer, default=0, nullable=False)
    device_info = db.Column(json_type, default=dict, nullable=False)
    ip_address = db.Column(db.String(80))
    started_at = db.Column(db.DateTime(timezone=True))
    ended_at = db.Column(db.DateTime(timezone=True))

    attempt = db.relationship("AssessmentAttempt", back_populates="proctoring_session")
    events = db.relationship("ProctoringEvent", back_populates="session", cascade="all, delete-orphan", order_by="ProctoringEvent.occurred_at")


class ProctoringEvent(db.Model):
    __tablename__ = "proctoring_events"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    session_id = db.Column(db.String(36), db.ForeignKey("proctoring_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = db.Column(db.String(60), nullable=False, index=True)  # fullscreen_exit | tab_switch | focus_loss | copy_paste | face_not_detected | multiple_faces | mobile_detected | camera_disabled | identity_check
    severity = db.Column(db.String(20), nullable=False, default="low")  # low | medium | high
    description = db.Column(db.String(500))
    event_metadata = db.Column(json_type, default=dict, nullable=False)
    reviewed = db.Column(db.Boolean, default=False, nullable=False)
    reviewer_note = db.Column(db.Text)
    occurred_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    session = db.relationship("ProctoringSession", back_populates="events")


# ─────────────────────────────────────────────
# Phase 5 — AI-Assisted First-Round Interview
# ─────────────────────────────────────────────

class AIInterviewQuestionTemplate(db.Model, TimestampMixin):
    __tablename__ = "ai_interview_question_templates"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = db.Column(db.String(40), nullable=False, default="mcq", index=True)
    category = db.Column(db.String(40), nullable=False, default="technical", index=True)
    content = db.Column(db.Text, nullable=False)
    options = db.Column(json_type, default=list, nullable=False)
    correct_answer = db.Column(db.Text)
    marks = db.Column(db.Integer, nullable=False, default=1)
    difficulty = db.Column(db.String(40), nullable=False, default="standard")
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"))

    job = db.relationship("Job", foreign_keys=[job_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

class AIInterview(db.Model, TimestampMixin):
    __tablename__ = "ai_interviews"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    application_id = db.Column(db.String(36), db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="scheduled", index=True)  # scheduled | identity_verified | in_progress | completed | reviewed
    invitation_sent_at = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    total_duration_seconds = db.Column(db.Integer)
    mcq_config = db.Column(json_type, default=dict, nullable=False)
    proctoring_summary = db.Column(json_type, default=dict, nullable=False)
    security_events = db.Column(json_type, default=list, nullable=False)
    admin_messages = db.Column(json_type, default=list, nullable=False)
    latest_frame_data_url = db.Column(db.Text)
    latest_frame_at = db.Column(db.DateTime(timezone=True))
    recording_path = db.Column(db.String(700))
    ai_summary = db.Column(json_type, default=dict, nullable=False)
    ai_scores = db.Column(json_type, default=dict, nullable=False)
    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    reviewer_notes = db.Column(db.Text)
    recommendation = db.Column(db.String(40))  # Proceed | Hold | Reject

    application = db.relationship("Application", foreign_keys=[application_id])
    candidate = db.relationship("User", foreign_keys=[candidate_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    questions = db.relationship("AIInterviewQuestion", back_populates="interview", cascade="all, delete-orphan", order_by="AIInterviewQuestion.order")
    responses = db.relationship("AIInterviewResponse", back_populates="interview", cascade="all, delete-orphan")


class AIInterviewQuestion(db.Model):
    __tablename__ = "ai_interview_questions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    interview_id = db.Column(db.String(36), db.ForeignKey("ai_interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    question_type = db.Column(db.String(40), nullable=False, default="technical")
    category = db.Column(db.String(40), nullable=False, default="technical")
    content = db.Column(db.Text, nullable=False)
    options = db.Column(json_type, default=list, nullable=False)
    correct_answer = db.Column(db.Text)
    marks = db.Column(db.Integer, nullable=False, default=1)
    context = db.Column(db.Text)
    asked_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    interview = db.relationship("AIInterview", back_populates="questions")
    response = db.relationship("AIInterviewResponse", back_populates="question", uselist=False, cascade="all, delete-orphan")


class AIInterviewResponse(db.Model):
    __tablename__ = "ai_interview_responses"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    interview_id = db.Column(db.String(36), db.ForeignKey("ai_interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("ai_interview_questions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    response_text = db.Column(db.Text)
    is_correct = db.Column(db.Boolean)
    response_audio_path = db.Column(db.String(700))
    response_duration_seconds = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    ai_quality_notes = db.Column(json_type, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    interview = db.relationship("AIInterview", back_populates="responses")
    question = db.relationship("AIInterviewQuestion", back_populates="response")
