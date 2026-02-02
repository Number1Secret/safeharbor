"""
Email Service

SMTP/SendGrid abstraction for transactional emails.
Supports user invitations, calculation alerts, anomaly warnings, and sync failure alerts.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Email settings with defaults
SMTP_HOST = getattr(settings, "smtp_host", "")
SMTP_PORT = getattr(settings, "smtp_port", 587)
SMTP_USER = getattr(settings, "smtp_user", "")
SMTP_PASSWORD = getattr(settings, "smtp_password", "")
FROM_EMAIL = getattr(settings, "from_email", "notifications@safeharbor.ai")
FROM_NAME = "SafeHarbor AI"


def _send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """
    Send an email via SMTP.

    Returns True if sent successfully, False otherwise.
    In development mode (no SMTP configured), logs the email instead.
    """
    if not SMTP_HOST:
        logger.info(f"[EMAIL-DEV] To: {to} | Subject: {subject}")
        logger.debug(f"[EMAIL-DEV] Body: {text_body or html_body[:200]}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to, msg.as_string())

        logger.info(f"Email sent to {to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


# ── Template Functions ─────────────────────────────


def send_invite_email(to_email: str, invite_token: str, org_name: str, inviter_name: str) -> bool:
    """Send a user invitation email."""
    subject = f"You've been invited to {org_name} on SafeHarbor AI"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">Welcome to SafeHarbor AI</h2>
        <p>{inviter_name} has invited you to join <strong>{org_name}</strong> on SafeHarbor AI.</p>
        <p>SafeHarbor AI automates OBBB tax compliance calculations, ensuring your organization
        claims the correct qualified overtime, tip, and senior citizen wage exemptions.</p>
        <p><a href="https://app.safeharbor.ai/invite/{invite_token}"
              style="display: inline-block; padding: 12px 24px; background: #1e40af;
                     color: white; text-decoration: none; border-radius: 6px;">
            Accept Invitation
        </a></p>
        <p style="color: #666; font-size: 12px;">This invitation expires in 7 days.</p>
    </div>
    """
    text = (
        f"{inviter_name} has invited you to join {org_name} on SafeHarbor AI.\n\n"
        f"Accept: https://app.safeharbor.ai/invite/{invite_token}\n\n"
        f"This invitation expires in 7 days."
    )
    return _send_email(to_email, subject, html, text)


def send_approval_reminder_email(
    to_email: str, org_name: str, run_id: str, period: str
) -> bool:
    """Send calculation run approval reminder."""
    subject = f"[SafeHarbor] Calculation run pending approval — {org_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">Approval Required</h2>
        <p>A calculation run for <strong>{org_name}</strong> is ready for review.</p>
        <table style="border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px; color: #666;">Run ID:</td>
                <td style="padding: 8px;"><code>{run_id[:8]}...</code></td></tr>
            <tr><td style="padding: 8px; color: #666;">Period:</td>
                <td style="padding: 8px;">{period}</td></tr>
        </table>
        <p><a href="https://app.safeharbor.ai/calculations/{run_id}"
              style="display: inline-block; padding: 12px 24px; background: #1e40af;
                     color: white; text-decoration: none; border-radius: 6px;">
            Review Calculation
        </a></p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_sync_failure_email(
    to_email: str, org_name: str, provider: str, error_message: str
) -> bool:
    """Send integration sync failure alert."""
    subject = f"[SafeHarbor] {provider} sync failed — {org_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #dc2626;">Sync Failure Alert</h2>
        <p>The <strong>{provider}</strong> integration for <strong>{org_name}</strong> has failed.</p>
        <div style="background: #fef2f2; border-left: 4px solid #dc2626;
                    padding: 12px; margin: 16px 0;">
            <code>{error_message}</code>
        </div>
        <p>Please check the integration settings in your SafeHarbor dashboard.</p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_anomaly_alert_email(
    to_email: str, org_name: str, employee_name: str, anomaly_type: str, details: str
) -> bool:
    """Send calculation anomaly alert."""
    subject = f"[SafeHarbor] Anomaly detected — {org_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #d97706;">Anomaly Detected</h2>
        <p>An anomaly was detected during calculations for <strong>{org_name}</strong>.</p>
        <table style="border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px; color: #666;">Employee:</td>
                <td style="padding: 8px;">{employee_name}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Type:</td>
                <td style="padding: 8px;">{anomaly_type}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Details:</td>
                <td style="padding: 8px;">{details}</td></tr>
        </table>
        <p>Please review the calculation results for accuracy.</p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_phase_out_warning_email(
    to_email: str, org_name: str, employee_name: str, current_magi: str, threshold: str
) -> bool:
    """Send MAGI phase-out warning."""
    subject = f"[SafeHarbor] Phase-out warning — {employee_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #d97706;">Phase-Out Warning</h2>
        <p>An employee at <strong>{org_name}</strong> is approaching the MAGI phase-out threshold.</p>
        <table style="border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px; color: #666;">Employee:</td>
                <td style="padding: 8px;">{employee_name}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Current MAGI:</td>
                <td style="padding: 8px;">${current_magi}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Threshold:</td>
                <td style="padding: 8px;">${threshold}</td></tr>
        </table>
        <p>Tax credit amounts will be reduced as income exceeds the phase-out threshold.</p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_writeback_confirmation_email(
    to_email: str, org_name: str, records_count: int, provider: str
) -> bool:
    """Send write-back confirmation email."""
    subject = f"[SafeHarbor] Write-back complete — {org_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #059669;">Write-Back Complete</h2>
        <p>W-2 Box 12 values have been successfully written back to
        <strong>{provider}</strong> for <strong>{org_name}</strong>.</p>
        <p style="font-size: 24px; color: #059669; font-weight: bold;">
            {records_count} records updated
        </p>
    </div>
    """
    return _send_email(to_email, subject, html)
