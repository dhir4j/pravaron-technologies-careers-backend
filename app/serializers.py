from __future__ import annotations

from datetime import datetime

from .models import (
    AIInterview, AIInterviewQuestion, AIInterviewQuestionTemplate, AIInterviewResponse,
    ApplicantDetail, Application, ApplicationGroup, ApplicationGroupEmail, ApplicationGroupMember, Assessment, AssessmentAttempt,
    AssessmentQuestion, AssessmentResponse, CandidateAnalysis,
    CandidateProfile, InconsistencyFlag, Interview, InterviewFeedback,
    Job, Notification, OfferLetter, ProctoringEvent, ProctoringSession, Resume, User,
)


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


def applicant_detail_to_dict(detail: ApplicantDetail | None, include_resume_text: bool = False) -> dict | None:
    if not detail:
        return None
    return {
        "id": detail.id,
        "application_id": detail.application_id,
        "candidate_id": detail.candidate_id,
        "resume_id": detail.resume_id,
        "source": detail.source,
        "full_name": detail.full_name,
        "email": detail.email,
        "phone": detail.phone,
        "current_city": detail.current_city,
        "current_role": detail.current_role,
        "linkedin_url": detail.linkedin_url,
        "github_url": detail.github_url,
        "portfolio_url": detail.portfolio_url,
        "email_subject": detail.email_subject,
        "email_message_id": detail.email_message_id,
        "email_sent_at": detail.email_sent_at,
        "resume_filename": detail.resume_filename,
        "resume_content_type": detail.resume_content_type,
        "resume_size_bytes": detail.resume_size_bytes,
        "resume_text": detail.resume_text if include_resume_text else None,
        "resume_text_length": len(detail.resume_text or ""),
        "parsed_fields": detail.parsed_fields or {},
        "extraction_status": detail.extraction_status,
        "extraction_error": detail.extraction_error,
        "created_at": iso(detail.created_at),
        "updated_at": iso(detail.updated_at),
    }
def candidate_analysis_to_dict(analysis: CandidateAnalysis | None) -> dict | None:
    if not analysis:
        return None
    return {
        "id": analysis.id,
        "application_id": analysis.application_id,
        "applicant_detail_id": analysis.applicant_detail_id,
        "candidate_id": analysis.candidate_id,
        "resume_id": analysis.resume_id,
        "job_id": analysis.job_id,
        "model": analysis.model,
        "status": analysis.status,
        "suitability_score": analysis.suitability_score,
        "confidence_score": analysis.confidence_score,
        "recommendation": analysis.recommendation,
        "graduation_year": analysis.graduation_year,
        "recommended_track": analysis.recommended_track,
        "location_priority": analysis.location_priority,
        "detected_location": analysis.detected_location,
        "job_family": analysis.job_family,
        "headline": analysis.headline,
        "summary": analysis.summary,
        "experience_summary": analysis.experience_summary,
        "education_summary": analysis.education_summary,
        "projects_summary": analysis.projects_summary,
        "skills": analysis.skills or [],
        "languages": analysis.languages or [],
        "frameworks": analysis.frameworks or [],
        "tools": analysis.tools or [],
        "strengths": analysis.strengths or [],
        "concerns": analysis.concerns or [],
        "project_highlights": analysis.project_highlights or [],
        "job_fit": analysis.job_fit or {},
        "interview_questions": analysis.interview_questions or [],
        "usage": analysis.usage or {},
        "error": analysis.error,
        "analyzed_at": iso(analysis.analyzed_at),
        "created_at": iso(analysis.created_at),
        "updated_at": iso(analysis.updated_at),
    }
def application_to_dict(application: Application, include_private: bool = False, include_applicant_detail_text: bool = False) -> dict:
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
        email_info = (application.answers or {}).get("email") if isinstance(application.answers, dict) else None
        data.update(
            {
                "candidate": user_to_dict(application.candidate) if application.candidate else None,
                "declarations": application.declarations or {},
                "rejection_reason": application.rejection_reason,
                "withdrawal_reason": application.withdrawal_reason,
                "email": email_info if isinstance(email_info, dict) else None,
                "applicant_detail": applicant_detail_to_dict(application.applicant_detail, include_resume_text=include_applicant_detail_text),
                "candidate_analysis": candidate_analysis_to_dict(application.candidate_analysis),
            }
        )
    return data



def application_group_email_to_dict(email: ApplicationGroupEmail) -> dict:
    return {
        "id": email.id,
        "group_id": email.group_id,
        "application_id": email.application_id,
        "candidate_id": email.candidate_id,
        "to_email": email.to_email,
        "subject": email.subject,
        "purpose": email.purpose,
        "status_to_apply": email.status_to_apply,
        "delivery_status": email.delivery_status,
        "failure_reason": email.failure_reason,
        "sent_at": iso(email.sent_at),
        "created_at": iso(email.created_at),
    }


def application_group_member_to_dict(member: ApplicationGroupMember) -> dict:
    application = member.application
    candidate = application.candidate if application else None
    job = application.job if application else None
    return {
        "id": member.id,
        "group_id": member.group_id,
        "application_id": member.application_id,
        "candidate_name": candidate.full_name if candidate else None,
        "candidate_email": candidate.email if candidate else None,
        "job_title": job.title if job else None,
        "application_status": application.internal_status if application else None,
        "added_by_id": member.added_by_id,
        "created_at": iso(member.created_at),
    }


def application_group_to_dict(group: ApplicationGroup, include_members: bool = False, include_emails: bool = False) -> dict:
    data = {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "status": group.status,
        "created_by_id": group.created_by_id,
        "member_count": len(group.members or []),
        "created_at": iso(group.created_at),
        "updated_at": iso(group.updated_at),
    }
    if include_members:
        data["members"] = [application_group_member_to_dict(member) for member in group.members]
    if include_emails:
        emails = ApplicationGroupEmail.query.filter_by(group_id=group.id).order_by(ApplicationGroupEmail.created_at.desc()).all()
        data["emails"] = [application_group_email_to_dict(email) for email in emails]
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


def interview_feedback_to_dict(feedback: InterviewFeedback | None) -> dict | None:
    if not feedback:
        return None
    return {
        "id": feedback.id,
        "interview_id": feedback.interview_id,
        "reviewer_id": feedback.reviewer_id,
        "technical_score": feedback.technical_score,
        "communication_score": feedback.communication_score,
        "problem_solving_score": feedback.problem_solving_score,
        "cultural_fit_score": feedback.cultural_fit_score,
        "overall_recommendation": feedback.overall_recommendation,
        "strengths": feedback.strengths,
        "concerns": feedback.concerns,
        "notes": feedback.notes,
        "created_at": iso(feedback.created_at),
        "updated_at": iso(feedback.updated_at),
    }


def offer_letter_to_dict(offer: OfferLetter | None) -> dict | None:
    if not offer:
        return None
    return {
        "id": offer.id,
        "application_id": offer.application_id,
        "created_by_id": offer.created_by_id,
        "role_title": offer.role_title,
        "department": offer.department,
        "joining_date": offer.joining_date.isoformat() if offer.joining_date else None,
        "compensation_details": offer.compensation_details,
        "additional_terms": offer.additional_terms,
        "status": offer.status,
        "sent_at": iso(offer.sent_at),
        "responded_at": iso(offer.responded_at),
        "created_at": iso(offer.created_at),
        "updated_at": iso(offer.updated_at),
    }


def inconsistency_flag_to_dict(flag: InconsistencyFlag | None) -> dict | None:
    if not flag:
        return None
    return {
        "id": flag.id,
        "application_id": flag.application_id,
        "flags": flag.flags or [],
        "reviewed": flag.reviewed,
        "reviewer_note": flag.reviewer_note,
        "detected_at": iso(flag.detected_at),
        "created_at": iso(flag.created_at),
    }


def assessment_question_to_dict(question: AssessmentQuestion, include_answer: bool = False) -> dict:
    return {
        "id": question.id,
        "assessment_id": question.assessment_id,
        "question_type": question.question_type,
        "content": question.content,
        "options": question.options or [],
        "correct_answer": question.correct_answer if include_answer else None,
        "explanation": question.explanation if include_answer else None,
        "marks": question.marks,
        "order": question.order,
        "time_limit_seconds": question.time_limit_seconds,
        "code_template": question.code_template,
        "code_language": question.code_language,
        "created_at": iso(question.created_at),
    }


def assessment_to_dict(assessment: Assessment, include_questions: bool = False, include_answers: bool = False) -> dict:
    data = {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "assessment_type": assessment.assessment_type,
        "job_id": assessment.job_id,
        "time_limit_minutes": assessment.time_limit_minutes,
        "max_attempts": assessment.max_attempts,
        "pass_score": assessment.pass_score,
        "randomize_questions": assessment.randomize_questions,
        "instructions": assessment.instructions,
        "status": assessment.status,
        "created_by_id": assessment.created_by_id,
        "question_count": len(assessment.questions),
        "total_marks": sum(q.marks for q in assessment.questions),
        "created_at": iso(assessment.created_at),
        "updated_at": iso(assessment.updated_at),
    }
    if include_questions:
        data["questions"] = [assessment_question_to_dict(q, include_answer=include_answers) for q in assessment.questions]
    return data


def assessment_response_to_dict(response: AssessmentResponse, include_question: bool = False) -> dict:
    data = {
        "id": response.id,
        "attempt_id": response.attempt_id,
        "question_id": response.question_id,
        "response": response.response,
        "is_correct": response.is_correct,
        "auto_marks": response.auto_marks,
        "time_taken_seconds": response.time_taken_seconds,
        "manual_marks": response.manual_marks,
        "reviewer_comment": response.reviewer_comment,
        "reviewed_by_id": response.reviewed_by_id,
        "created_at": iso(response.created_at),
    }
    if include_question:
        data["question"] = assessment_question_to_dict(response.question, include_answer=True)
    return data


def attempt_to_dict(attempt: AssessmentAttempt, include_responses: bool = False) -> dict:
    data = {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "application_id": attempt.application_id,
        "candidate_id": attempt.candidate_id,
        "status": attempt.status,
        "started_at": iso(attempt.started_at),
        "submitted_at": iso(attempt.submitted_at),
        "expires_at": iso(attempt.expires_at),
        "auto_score": attempt.auto_score,
        "max_auto_score": attempt.max_auto_score,
        "manual_score": attempt.manual_score,
        "final_score": attempt.final_score,
        "percentage": attempt.percentage,
        "is_passed": attempt.is_passed,
        "graded_by_id": attempt.graded_by_id,
        "graded_at": iso(attempt.graded_at),
        "grader_notes": attempt.grader_notes,
        "created_at": iso(attempt.created_at),
        "updated_at": iso(attempt.updated_at),
    }
    if include_responses:
        data["responses"] = [assessment_response_to_dict(r, include_question=True) for r in attempt.responses]
    return data


def proctoring_event_to_dict(event: ProctoringEvent) -> dict:
    return {
        "id": event.id,
        "session_id": event.session_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "description": event.description,
        "metadata": event.metadata or {},
        "reviewed": event.reviewed,
        "reviewer_note": event.reviewer_note,
        "occurred_at": iso(event.occurred_at),
    }


def proctoring_session_to_dict(session: ProctoringSession, include_events: bool = False) -> dict:
    data = {
        "id": session.id,
        "attempt_id": session.attempt_id,
        "fullscreen_exits": session.fullscreen_exits,
        "tab_switches": session.tab_switches,
        "focus_losses": session.focus_losses,
        "copy_paste_events": session.copy_paste_events,
        "face_not_detected_count": session.face_not_detected_count,
        "multiple_faces_count": session.multiple_faces_count,
        "mobile_detected_count": session.mobile_detected_count,
        "suspicious_total": session.suspicious_total,
        "device_info": session.device_info or {},
        "ip_address": session.ip_address,
        "started_at": iso(session.started_at),
        "ended_at": iso(session.ended_at),
        "created_at": iso(session.created_at),
    }
    if include_events:
        data["events"] = [proctoring_event_to_dict(e) for e in session.events]
    return data



def ai_interview_question_template_to_dict(template: AIInterviewQuestionTemplate) -> dict:
    return {
        "id": template.id,
        "job_id": template.job_id,
        "job_title": template.job.title if template.job else None,
        "mode": template.mode,
        "category": template.category,
        "content": template.content,
        "options": template.options or [],
        "correct_answer": template.correct_answer,
        "marks": template.marks,
        "difficulty": template.difficulty,
        "is_active": template.is_active,
        "order": template.order,
        "created_by_id": template.created_by_id,
        "created_at": iso(template.created_at),
        "updated_at": iso(template.updated_at),
    }
def ai_interview_question_to_dict(question: AIInterviewQuestion, include_response: bool = False) -> dict:
    data = {
        "id": question.id,
        "interview_id": question.interview_id,
        "order": question.order,
        "question_type": question.question_type,
        "category": question.category,
        "content": question.content,
        "options": question.options or [],
        "marks": question.marks,
        "context": question.context,
        "asked_at": iso(question.asked_at),
    }
    if include_response:
        data["correct_answer"] = question.correct_answer
    if include_response and question.response:
        r = question.response
        data["response"] = {
            "id": r.id,
            "response_text": r.response_text,
            "is_correct": r.is_correct,
            "response_duration_seconds": r.response_duration_seconds,
            "submitted_at": iso(r.submitted_at),
            "ai_quality_notes": r.ai_quality_notes or {},
        }
    return data


def ai_interview_to_dict(interview: AIInterview, include_transcript: bool = False) -> dict:
    candidate = interview.candidate if hasattr(interview, "candidate") else None
    application = interview.application if hasattr(interview, "application") else None
    job = application.job if application else None
    data = {
        "id": interview.id,
        "application_id": interview.application_id,
        "candidate_id": interview.candidate_id,
        "candidate_name": candidate.full_name if candidate else None,
        "candidate_email": candidate.email if candidate else None,
        "job_title": job.title if job else None,
        "status": interview.status,
        "invitation_sent_at": iso(interview.invitation_sent_at),
        "started_at": iso(interview.started_at),
        "completed_at": iso(interview.completed_at),
        "total_duration_seconds": interview.total_duration_seconds,
        "mcq_config": {k: v for k, v in (interview.mcq_config or {}).items() if k != "access_code"},
        "proctoring_summary": interview.proctoring_summary or {},
        "security_events": (interview.security_events or [])[-50:],
        "admin_messages": interview.admin_messages or [],
        "latest_frame_at": iso(interview.latest_frame_at),
        "recording_available": bool(interview.recording_path),
        "ai_summary": interview.ai_summary or {},
        "ai_scores": interview.ai_scores or {},
        "reviewed_by_id": interview.reviewed_by_id,
        "reviewed_at": iso(interview.reviewed_at),
        "reviewer_notes": interview.reviewer_notes,
        "recommendation": interview.recommendation,
        "question_count": len(interview.questions),
        "created_at": iso(interview.created_at),
        "updated_at": iso(interview.updated_at),
    }
    if include_transcript:
        data["questions"] = [ai_interview_question_to_dict(q, include_response=True) for q in interview.questions]
        data["latest_frame_data_url"] = interview.latest_frame_data_url
    return data
