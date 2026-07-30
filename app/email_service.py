from __future__ import annotations

import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from flask import current_app, render_template_string

from .extensions import db
from .models import Notification


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def render_email_template(template_body: str, variables: dict[str, Any]) -> str:
    """Render email template with variable substitution."""
    rendered = template_body
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        rendered = rendered.replace(placeholder, str(value))
    return rendered


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
    notification_id: str | None = None,
) -> bool:
    """
    Send email using configured SMTP settings.
    Returns True if successful, False otherwise.
    Updates notification status if notification_id provided.
    """
    try:
        # Get SMTP configuration from environment
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("FROM_EMAIL", smtp_user)
        from_name = os.getenv("FROM_NAME", "Pravaron Careers")

        if not smtp_user or not smtp_password:
            current_app.logger.error("SMTP credentials not configured")
            if notification_id:
                _update_notification_failed(notification_id, "SMTP credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        # Add plain text version (fallback)
        if plain_body is None:
            # Strip HTML tags for plain text version
            import re
            plain_body = re.sub(r"<[^>]+>", "", html_body)
            plain_body = re.sub(r"\s+", " ", plain_body).strip()

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        current_app.logger.info(f"Email sent successfully to {to_email}")

        # Update notification status
        if notification_id:
            _update_notification_sent(notification_id)

        return True

    except smtplib.SMTPAuthenticationError as e:
        current_app.logger.error(f"SMTP authentication failed: {e}")
        if notification_id:
            _update_notification_failed(notification_id, "Authentication failed")
        return False

    except smtplib.SMTPException as e:
        current_app.logger.error(f"SMTP error sending email to {to_email}: {e}")
        if notification_id:
            _update_notification_failed(notification_id, str(e))
        return False

    except Exception as e:
        current_app.logger.error(f"Unexpected error sending email to {to_email}: {e}")
        if notification_id:
            _update_notification_failed(notification_id, str(e))
        return False


def _update_notification_sent(notification_id: str) -> None:
    """Update notification status to sent."""
    try:
        notification = db.session.get(Notification, notification_id)
        if notification:
            notification.delivery_status = "sent"
            notification.sent_at = utcnow()
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to update notification {notification_id}: {e}")
        db.session.rollback()


def _update_notification_failed(notification_id: str, reason: str) -> None:
    """Update notification status to failed."""
    try:
        notification = db.session.get(Notification, notification_id)
        if notification:
            notification.delivery_status = "failed"
            notification.failure_reason = reason[:500]  # Limit length
            notification.retry_count = (notification.retry_count or 0) + 1
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to update notification {notification_id}: {e}")
        db.session.rollback()


def get_email_template_variables(user, application=None, job=None, interview=None) -> dict[str, str]:
    """Build common template variables for email rendering."""
    variables = {
        "candidate_name": user.full_name,
        "candidate_email": user.email,
        "company_name": "Pravaron Technologies",
        "careers_url": os.getenv("CAREERS_PUBLIC_URL", "https://careers.pravarontechnologies.com"),
        "support_email": "careers@example.com",
    }

    if application:
        variables.update(
            {
                "application_id": application.id,
                "application_status": application.candidate_status,
                "application_url": f"{variables['careers_url']}/candidate/applications/{application.id}",
            }
        )

    if job:
        variables.update(
            {
                "job_title": job.title,
                "job_code": job.public_code,
                "job_url": f"{variables['careers_url']}/jobs/{job.slug}",
            }
        )

    if interview:
        variables.update(
            {
                "interview_date": interview.starts_at.strftime("%B %d, %Y") if interview.starts_at else "TBD",
                "interview_time": interview.starts_at.strftime("%I:%M %p") if interview.starts_at else "TBD",
                "interview_timezone": interview.timezone or "IST",
                "meeting_link": interview.meeting_link or "Will be provided",
            }
        )

    return variables


# Email HTML templates
EMAIL_BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #151515; margin: 0; padding: 0; background-color: #f5f5f4; }}
        .email-container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
        .email-header {{ background-color: #d72a21; color: #ffffff; padding: 32px 24px; text-align: center; }}
        .email-header h1 {{ margin: 0; font-size: 24px; font-weight: 700; }}
        .email-body {{ padding: 32px 24px; }}
        .email-body h2 {{ font-size: 20px; margin-top: 0; color: #151515; }}
        .email-body p {{ margin: 16px 0; color: #282828; }}
        .button {{ display: inline-block; padding: 14px 28px; background-color: #d72a21; color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: 700; margin: 24px 0; }}
        .info-box {{ background-color: #f5f5f4; border-left: 4px solid #d72a21; padding: 16px; margin: 24px 0; }}
        .footer {{ background-color: #171717; color: rgba(255,255,255,0.7); padding: 24px; text-align: center; font-size: 12px; }}
        .footer a {{ color: rgba(255,255,255,0.9); text-decoration: none; }}
        .divider {{ border-top: 1px solid #ededeb; margin: 24px 0; }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <h1>Pravaron Careers</h1>
        </div>
        <div class="email-body">
            {content}
        </div>
        <div class="footer">
            <p><strong>Pravaron Technologies</strong></p>
            <p>O-621, Block-A, EON Fairfox, Sector-140A, Noida</p>
            <p><a href="mailto:careers@example.com">careers@example.com</a></p>
            <div class="divider"></div>
            <p>© 2026 Pravaron Technologies Pvt. Ltd. · Noida, India</p>
        </div>
    </div>
</body>
</html>
"""


def get_verification_email(user, verification_url: str) -> tuple[str, str]:
    """Generate email verification email."""
    subject = "Verify your Pravaron Careers account"

    content = f"""
        <h2>Welcome to Pravaron Careers!</h2>
        <p>Hi {user.full_name},</p>
        <p>Thank you for registering with Pravaron Careers. Please verify your email address to complete your registration and start applying for positions.</p>
        <p style="text-align: center;">
            <a href="{verification_url}" class="button">Verify Email Address</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #686868; font-size: 13px;">{verification_url}</p>
        <div class="divider"></div>
        <p><strong>Why verify?</strong></p>
        <p>Email verification helps us ensure the security of your account and enables us to send you important updates about your applications.</p>
        <p style="color: #686868; font-size: 13px;">If you didn't create this account, you can safely ignore this email.</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body


def get_application_submitted_email(user, application, job) -> tuple[str, str]:
    """Generate application submitted confirmation email."""
    variables = get_email_template_variables(user, application, job)
    subject = f"Application received for {job.title}"

    content = f"""
        <h2>Application Submitted Successfully</h2>
        <p>Hi {variables['candidate_name']},</p>
        <p>Thank you for applying for the <strong>{variables['job_title']}</strong> position at Pravaron Technologies.</p>

        <div class="info-box">
            <p style="margin: 0;"><strong>Application ID:</strong> {variables['application_id']}</p>
            <p style="margin: 8px 0 0 0;"><strong>Position:</strong> {variables['job_title']}</p>
        </div>

        <p>Your application has been received and will be reviewed by our recruitment team. You can track the status of your application through your dashboard.</p>

        <p style="text-align: center;">
            <a href="{variables['application_url']}" class="button">View Application Status</a>
        </p>

        <p><strong>What happens next?</strong></p>
        <ul>
            <li>Our team will review your application</li>
            <li>You'll receive updates via email and in your dashboard</li>
            <li>If shortlisted, we'll contact you for the next steps</li>
        </ul>

        <p>We appreciate your interest in joining Pravaron Technologies!</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body


def get_status_update_email(user, application, job, old_status: str, new_status: str) -> tuple[str, str]:
    """Generate application status update email."""
    variables = get_email_template_variables(user, application, job)
    subject = f"Application update: {new_status}"

    status_messages = {
        "Under Initial Review": "Your application is currently under review by our recruitment team.",
        "Shortlisted": "Congratulations! Your application has been shortlisted. We'll contact you soon with next steps.",
        "Interview Scheduled": "An interview has been scheduled for your application. Please check your dashboard for details.",
        "Interview Completed": "Thank you for completing the interview. We're reviewing feedback and will update you soon.",
        "Final Review": "Your application is in final review. We'll notify you of the decision shortly.",
        "Offer Released": "Congratulations! We're pleased to extend an offer. Please check your dashboard for details.",
        "Not Selected": "Thank you for your interest. While we've decided to move forward with other candidates, we encourage you to apply for future opportunities.",
    }

    message = status_messages.get(new_status, f"Your application status has been updated to {new_status}.")

    content = f"""
        <h2>Application Status Update</h2>
        <p>Hi {variables['candidate_name']},</p>
        <p>Your application for <strong>{variables['job_title']}</strong> has been updated.</p>

        <div class="info-box">
            <p style="margin: 0;"><strong>Application ID:</strong> {variables['application_id']}</p>
            <p style="margin: 8px 0 0 0;"><strong>New Status:</strong> {new_status}</p>
        </div>

        <p>{message}</p>

        <p style="text-align: center;">
            <a href="{variables['application_url']}" class="button">View Full Details</a>
        </p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body


def get_interview_invitation_email(user, application, job, interview) -> tuple[str, str]:
    """Generate interview invitation email."""
    variables = get_email_template_variables(user, application, job, interview)
    subject = f"Interview invitation: {job.title}"

    content = f"""
        <h2>Interview Scheduled</h2>
        <p>Hi {variables['candidate_name']},</p>
        <p>We're pleased to invite you for an interview for the <strong>{variables['job_title']}</strong> position.</p>

        <div class="info-box">
            <p style="margin: 0;"><strong>Date:</strong> {variables['interview_date']}</p>
            <p style="margin: 8px 0 0 0;"><strong>Time:</strong> {variables['interview_time']} {variables['interview_timezone']}</p>
            <p style="margin: 8px 0 0 0;"><strong>Meeting Link:</strong> {variables['meeting_link']}</p>
        </div>

        <p style="text-align: center;">
            <a href="{variables['application_url']}" class="button">View Interview Details</a>
        </p>

        <p><strong>Interview Preparation:</strong></p>
        <ul>
            <li>Please test your video/audio setup before the interview</li>
            <li>Review your application and the job description</li>
            <li>Prepare examples of your relevant work and projects</li>
            <li>Have questions ready about the role and team</li>
        </ul>

        <p>If you need to reschedule, please contact us at least 24 hours in advance.</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body


def get_password_reset_email(user, reset_url: str) -> tuple[str, str]:
    """Generate password reset email."""
    subject = "Reset your Pravaron Careers password"

    content = f"""
        <h2>Password Reset Request</h2>
        <p>Hi {user.full_name},</p>
        <p>We received a request to reset your password for your Pravaron Careers account.</p>

        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password</a>
        </p>

        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #686868; font-size: 13px;">{reset_url}</p>

        <p><strong>This link will expire in 1 hour.</strong></p>

        <div class="divider"></div>

        <p style="color: #686868; font-size: 13px;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body


def get_ai_interview_invitation_email(user, application, job, interview_id: str, access_code: str | None = None) -> tuple[str, str]:
    """Generate secured interview invitation email."""
    careers_url = os.getenv("CAREERS_PUBLIC_URL", "https://careers.pravarontechnologies.com")
    interview_url = f"{careers_url}/interview/{interview_id}"
    job_title = job.title if job else "a position"
    code = str(access_code or "").strip().upper()
    subject = f"Your interview is ready: {job_title}"

    content = f"""
        <h2>Your Interview Has Been Scheduled</h2>
        <p>Hi {user.full_name},</p>
        <p>Congratulations on advancing in the selection process for <strong>{job_title}</strong> at Pravaron Technologies.</p>
        <p>You have been invited to complete your first-round interview. Use the secure code below when the interview page opens.</p>

        <div class="info-box" style="text-align: center;">
            <p style="margin: 0 0 8px 0; color: #686868; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em;"><strong>Interview code</strong></p>
            <p style="margin: 0; font-size: 28px; letter-spacing: 0.18em; font-weight: 800; color: #1f1f1f;">{code}</p>
        </div>

        <p style="text-align: center;">
            <a href="{interview_url}" class="button">Open Interview</a>
        </p>

        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #686868; font-size: 13px;">{interview_url}</p>

        <div class="divider"></div>

        <p><strong>Before you begin:</strong></p>
        <ul style="color: #282828;">
            <li>Find a quiet, well-lit space.</li>
            <li>Ensure your internet connection is stable.</li>
            <li>Allow camera access and keep the interview window fullscreen.</li>
            <li>Keep the interview code private. It is required to open your interview.</li>
        </ul>

        <p style="color: #686868; font-size: 13px;">Questions? Contact us at <a href="mailto:careers@example.com">careers@example.com</a>.</p>
    """

    html_body = EMAIL_BASE_TEMPLATE.format(content=content)
    return subject, html_body