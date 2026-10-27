"""Outgoing email. Uses SMTP when configured.

Without SMTP, development mode logs the message so the reset flow can be
demonstrated locally; any other environment logs an error instead and never
prints the message body.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    settings = get_settings()

    if not settings.smtp_configured:
        if settings.is_development:
            logger.warning("SMTP not configured; development email to=%s subject=%r\n%s", to, subject, body)
            return True
        logger.error("SMTP not configured; email to=%s subject=%r was not sent", to, subject)
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("email send failed to=%s error=%s", to, exc.__class__.__name__)
        return False
    return True


def send_password_reset_email(to: str, full_name: str, reset_link: str, expires_minutes: int) -> bool:
    body = (
        f"Hello {full_name},\n\n"
        "We received a request to reset your ResolveAI password.\n"
        f"Open this link to choose a new password (valid for {expires_minutes} minutes):\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can ignore this email; your password will not change.\n"
    )
    return send_email(to, "Reset your ResolveAI password", body)
