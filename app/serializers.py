from __future__ import annotations

from datetime import datetime

from .models import Application, CandidateProfile, Interview, Job, Notification, Resume, User


def iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def profile_to_dict(profile: CandidateProfile | None) -> dict:
    if not profile:
        return {}
    return {
        "phone": profile.phone,
        "current_city": profile.current_city,
        "state": profile.state,
        "country": profile.country,
        "preferred_work_location": profile.preferred_work_location,
        "current_role": profile.current_role,
        "total_experience_years": profile.total_experience_years,
        "current_company": profile.current_company,
        "notice_period": profile.notice_period,
        "current_compensation": profile.current_compensation,
        "expected_compensation": profile.expected_compensation,
        "skills": profile.skills or [],
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "portfolio_url": profile.portfolio_url,
        "personal_website_url": profile.personal_website_url,
        "metadata": profile.extra_metadata or {},
        "updated_at": iso(profile.updated_at),
    }


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_verified": user.is_verified,
        "profile": profile_to_dict(user.profile),
        "created_at": iso(user.created_at),
    }


def job_to_dict(job: Job, include_private: bool = False) -> dict:
    source_metadata = job.source_metadata or {}
    data = {
        "id": job.id,
        "public_code": job.public_code,
        "title": job.title,
        "slug": job.slug,
        "department": job.department,
        "employment_type": job.employment_type,
        "experience_level": job.experience_level,
        "openings": job.openings,
        "location": job.location,
        "workplace_model": job.workplace_model,
        "salary_display": job.salary_display,
        "min_salary": job.min_salary if job.salary_display != "hidden" else None,
        "max_salary": job.max_salary if job.salary_display != "hidden" else None,
        "currency": job.currency,
        "role_summary": job.role_summary,
        "responsibilities": job.responsibilities,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "education_preference": job.education_preference,
        "experience_requirement": job.experience_requirement,
        "content_sections": source_metadata.get("content_sections") or [],
        "application_status_text": source_metadata.get("application_status_text"),
        "application_questions": job.application_questions or [],
        "selection_process": job.selection_process,
        "application_deadline": iso(job.application_deadline),
        "publish_at": iso(job.publish_at),
        "status": job.status,
        "created_at": iso(job.created_at),
        "updated_at": iso(job.updated_at),
    }
    if include_private:
        data.update({"owner_id": job.owner_id, "created_by_id": job.created_by_id, "source_metadata": source_metadata})
    return data


def resume_to_dict(resume: Resume) -> dict:
    return {
        "id": resume.id,
        "original_filename": resume.original_filename,
        "content_type": resume.content_type,
        "size_bytes": resume.size_bytes,
        "checksum_sha256": resume.checksum_sha256,
        "version": resume.version,
        "scan_status": resume.scan_status,
        "created_at": iso(resume.created_at),
    }


def application_to_dict(application: Application, include_private: bool = False) -> dict:
    data = {
        "id": application.id,
        "candidate_id": application.candidate_id,
        "job_id": application.job_id,
        "job": job_to_dict(application.job) if application.job else None,
        "resume": resume_to_dict(application.resume) if application.resume else None,
        "cover_message": application.cover_message,
        "answers": application.answers or {},
        "source": application.source,
        "candidate_status": application.candidate_status,
        "internal_status": application.internal_status if include_private else None,
        "withdrawn_at": iso(application.withdrawn_at),
        "created_at": iso(application.created_at),
        "updated_at": iso(application.updated_at),
    }
    if include_private:
        data.update(
            {
                "candidate": user_to_dict(application.candidate) if application.candidate else None,
                "declarations": application.declarations or {},
                "rejection_reason": application.rejection_reason,
                "withdrawal_reason": application.withdrawal_reason,
            }
        )
    return data


def notification_to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "application_id": notification.application_id,
        "notification_type": notification.notification_type,
        "subject": notification.subject,
        "message": notification.message,
        "channel": notification.channel,
        "delivery_status": notification.delivery_status,
        "sent_at": iso(notification.sent_at),
        "read_at": iso(notification.read_at),
        "created_at": iso(notification.created_at),
    }


def interview_to_dict(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "application_id": interview.application_id,
        "candidate_id": interview.candidate_id,
        "interviewer_id": interview.interviewer_id,
        "interview_type": interview.interview_type,
        "starts_at": iso(interview.starts_at),
        "ends_at": iso(interview.ends_at),
        "timezone": interview.timezone,
        "meeting_mode": interview.meeting_mode,
        "meeting_link": interview.meeting_link,
        "physical_location": interview.physical_location,
        "candidate_instructions": interview.candidate_instructions,
        "status": interview.status,
    }
