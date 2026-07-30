from __future__ import annotations

import os
from typing import Any

from flask import current_app

from .email_service import (
    get_ai_interview_invitation_email,
    get_application_submitted_email,
    get_interview_invitation_email,
    get_password_reset_email,
    get_status_update_email,
    get_verification_email,
    send_email,
)
from .extensions import db
from .models import AIInterview, Application, Interview, Job, Notification, User, utcnow


def _candidate_allows_email(user: User | None, notification_type: str, application_id: str | None, email_data: dict[str, Any]) -> bool:
    if not user:
        return False
    profile = user.profile
    prefs = profile.extra_metadata if profile and isinstance(profile.extra_metadata, dict) else {}
    if notification_type == "application_status_changed":
        new_status = str(email_data.get("new_status") or "")
        application = db.session.get(Application, application_id) if application_id else None
        candidate_status = new_status or (application.candidate_status if application else "")
        if candidate_status == "Offer Released":
            return prefs.get("email_on_offer", True) is not False
        return prefs.get("email_on_status_change", True) is not False
    if notification_type in {"interview_scheduled", "ai_interview_invitation"}:
        return prefs.get("email_on_interview", True) is not False
    if notification_type == "offer_response":
        return prefs.get("email_on_offer", True) is not False
    return True

def create_and_send_notification(
    recipient_id: str,
    subject: str,
    message: str,
    notification_type: str,
    application_id: str | None = None,
    send_email_flag: bool = True,
    email_data: dict[str, Any] | None = None,
) -> Notification:
    """
    Create notification and optionally send email.
    Returns the notification object.
    """
    # Create in-app notification
    notification = Notification(
        recipient_id=recipient_id,
        application_id=application_id,
        subject=subject,
        message=message,
        notification_type=notification_type,
        channel="in_app",
        delivery_status="sent",
        sent_at=utcnow(),
    )
    db.session.add(notification)
    db.session.flush()

    user = db.session.get(User, recipient_id)
    email_allowed = _candidate_allows_email(user, notification_type, application_id, email_data or {})

    # Create email notification if requested and allowed by preferences
    if send_email_flag and email_allowed:
        email_notification = Notification(
            recipient_id=recipient_id,
            application_id=application_id,
            subject=subject,
            message=message,
            notification_type=notification_type,
            channel="email",
            delivery_status="queued",
        )
        db.session.add(email_notification)
        db.session.flush()

        # Send email asynchronously (or immediately for testing)
        try:
            _send_notification_email(email_notification.id, email_data or {})
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification: {e}")

    return notification


def _send_notification_email(notification_id: str, email_data: dict[str, Any]) -> None:
    """Send email for a notification."""
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.channel != "email":
        return

    user = db.session.get(User, notification.recipient_id)
    if not user:
        return

    notification_type = notification.notification_type
    subject = notification.subject
    html_body = None

    # Generate email based on notification type
    if notification_type == "email_verification":
        verification_token = email_data.get("verification_token")
        if verification_token:
            verification_url = f"{os.getenv('CAREERS_PUBLIC_URL')}/verify-email?token={verification_token}"
            subject, html_body = get_verification_email(user, verification_url)

    elif notification_type == "password_reset":
        reset_token = email_data.get("reset_token")
        if reset_token:
            reset_url = f"{os.getenv('CAREERS_PUBLIC_URL')}/reset-password?token={reset_token}"
            subject, html_body = get_password_reset_email(user, reset_url)

    elif notification_type == "application_submitted":
        application = db.session.get(Application, notification.application_id)
        if application:
            job = application.job
            subject, html_body = get_application_submitted_email(user, application, job)

    elif notification_type == "application_status_changed":
        application = db.session.get(Application, notification.application_id)
        if application:
            job = application.job
            old_status = email_data.get("old_status", "")
            new_status = application.candidate_status
            subject, html_body = get_status_update_email(user, application, job, old_status, new_status)

    elif notification_type == "interview_scheduled":
        application = db.session.get(Application, notification.application_id)
        interview_id = email_data.get("interview_id")
        if application and interview_id:
            job = application.job
            interview = db.session.get(Interview, interview_id)
            if interview:
                subject, html_body = get_interview_invitation_email(user, application, job, interview)

    elif notification_type == "ai_interview_invitation":
        application = db.session.get(Application, notification.application_id)
        ai_interview_id = email_data.get("ai_interview_id")
        if application and ai_interview_id:
            job = application.job
            ai_interview = db.session.get(AIInterview, ai_interview_id)
            access_code = (ai_interview.mcq_config or {}).get("access_code") if ai_interview else None
            subject, html_body = get_ai_interview_invitation_email(user, application, job, ai_interview_id, access_code)

    # Send the email if we have content
    if html_body:
        send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            notification_id=notification_id,
        )
    else:
        # Fallback: mark as failed if we couldn't generate email
        notification.delivery_status = "failed"
        notification.failure_reason = "No email template for notification type"
        db.session.commit()


def send_verification_email(user: User, verification_token: str) -> None:
    """Send email verification email."""
    create_and_send_notification(
        recipient_id=user.id,
        subject="Verify your Pravaron Careers account",
        message="Please verify your email address to complete your registration.",
        notification_type="email_verification",
        send_email_flag=True,
        email_data={"verification_token": verification_token},
    )
    db.session.commit()


def send_application_submitted_notification(application: Application) -> None:
    """Send notification when application is submitted."""
    create_and_send_notification(
        recipient_id=application.candidate_id,
        subject=f"Application received for {application.job.title}",
        message=f"Your application for {application.job.title} has been received and will be reviewed by our team.",
        notification_type="application_submitted",
        application_id=application.id,
        send_email_flag=True,
    )
    db.session.commit()


def send_status_update_notification(
    application: Application, old_status: str, new_status: str
) -> None:
    """Send notification when application status changes."""
    create_and_send_notification(
        recipient_id=application.candidate_id,
        subject=f"Application status updated: {new_status}",
        message=f"Your application for {application.job.title} is now {new_status}.",
        notification_type="application_status_changed",
        application_id=application.id,
        send_email_flag=True,
        email_data={"old_status": old_status, "new_status": new_status},
    )
    db.session.commit()


def send_interview_invitation(application: Application, interview: Interview) -> None:
    """Send interview invitation notification."""
    create_and_send_notification(
        recipient_id=application.candidate_id,
        subject=f"Interview invitation: {application.job.title}",
        message=f"You have been invited for an interview for {application.job.title}. Please check the details in your dashboard.",
        notification_type="interview_scheduled",
        application_id=application.id,
        send_email_flag=True,
        email_data={"interview_id": interview.id},
    )
    db.session.commit()


def send_ai_interview_invitation(application: Application, ai_interview: AIInterview) -> None:
    """Send AI interview invitation notification and email."""
    job_title = application.job.title if application.job else "a position"
    create_and_send_notification(
        recipient_id=application.candidate_id,
        subject=f"Your interview is ready: {job_title}",
        message=f"You have been invited to complete a first-round interview for {job_title}. Use the code in your email to get started.",
        notification_type="ai_interview_invitation",
        application_id=application.id,
        send_email_flag=True,
        email_data={"ai_interview_id": ai_interview.id, "access_code": (ai_interview.mcq_config or {}).get("access_code")},
    )
    db.session.commit()


def send_password_reset_email(user: User, reset_token: str) -> None:
    """Send password reset email."""
    create_and_send_notification(
        recipient_id=user.id,
        subject="Reset your Pravaron Careers password",
        message="You requested to reset your password. Use the link in the email to reset it.",
        notification_type="password_reset",
        send_email_flag=True,
        email_data={"reset_token": reset_token},
    )
    db.session.commit()


def send_test_email(to_email: str = "darkcodix2008@gmail.com") -> bool:
    """Send a test email to verify SMTP configuration."""
    from .email_service import EMAIL_BASE_TEMPLATE, send_email

    subject = "Test Email from Pravaron Careers"

    content = """
        <h2>Email Service Test</h2>
        <p>Hi there,</p>
        <p>This is a test email to verify that the Pravaron Careers email service is working correctly.</p>

        <div class="info-box">
            <p style="margin: 0;"><strong>Status:</strong> Email service is operational ✓</p>
            <p style="margin: 8px 0 0 0;"><strong>SMTP Configuration:</strong> Connected successfully</p>
        </div>

        <p>If you're seeing this email, it means:</p>
        <ul>
            <li>SMTP connection is working</li>
            <li>Authentication is successful</li>
            <li>Email templates are rendering correctly</li>
            <li>The notification system is operational</li>
        </ul>

        <p>You can now proceed with testing other email notifications!</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)

    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )

