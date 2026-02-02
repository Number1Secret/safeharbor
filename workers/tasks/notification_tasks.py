"""
Notification Tasks

Background tasks for alerts, reminders, and notifications.
Uses the email service for delivery with async DB lookups for context.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from workers.celery_app import app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _get_org_contact(org_id: UUID) -> tuple[str | None, str]:
    """Look up org contact email and name."""
    from backend.db.session import get_async_session
    from backend.models.organization import Organization

    async with get_async_session() as session:
        result = await session.execute(
            select(Organization.primary_contact_email, Organization.name)
            .where(Organization.id == org_id)
        )
        row = result.first()
        if row and row[0]:
            return row[0], row[1]
        return None, row[1] if row else ""


async def _get_employee_name(employee_id: UUID) -> str:
    """Look up employee full name."""
    from backend.db.session import get_async_session
    from backend.models.employee import Employee

    async with get_async_session() as session:
        result = await session.execute(
            select(Employee.first_name, Employee.last_name)
            .where(Employee.id == employee_id)
        )
        row = result.first()
        if row:
            return f"{row[0]} {row[1]}"
        return "Unknown Employee"


async def _get_integration_provider(integration_id: UUID) -> str:
    """Look up integration provider name."""
    from backend.db.session import get_async_session
    from backend.models.integration import Integration

    async with get_async_session() as session:
        result = await session.execute(
            select(Integration.provider)
            .where(Integration.id == integration_id)
        )
        row = result.first()
        return row[0] if row else "Unknown Provider"


@app.task
def send_approval_reminder(organization_id: str, run_id: str):
    """Send reminder that a calculation run is pending approval."""
    logger.info(f"Sending approval reminder for run {run_id}")
    _run_async(_async_send_approval_reminder(UUID(organization_id), run_id))


@app.task
def send_sync_failure_alert(
    organization_id: str,
    integration_id: str,
    error_message: str,
):
    """Alert when an integration sync fails."""
    logger.warning(
        f"Sync failure alert: org={organization_id}, "
        f"integration={integration_id}, error={error_message}"
    )
    _run_async(
        _async_send_sync_alert(
            UUID(organization_id), UUID(integration_id), error_message
        )
    )


@app.task
def send_anomaly_alert(
    organization_id: str,
    employee_id: str,
    anomaly_type: str,
    details: dict,
):
    """Alert when a calculation anomaly is detected."""
    logger.warning(
        f"Anomaly detected: org={organization_id}, "
        f"employee={employee_id}, type={anomaly_type}"
    )
    _run_async(
        _async_send_anomaly_alert(
            UUID(organization_id), UUID(employee_id), anomaly_type,
            details.get("description", str(details)),
        )
    )


@app.task
def send_phase_out_warning(
    organization_id: str,
    employee_id: str,
    current_magi: str,
    threshold: str,
):
    """Warn when employee is approaching MAGI phase-out."""
    logger.info(
        f"Phase-out warning: employee={employee_id}, "
        f"MAGI={current_magi}, threshold={threshold}"
    )
    _run_async(
        _async_send_phase_out_warning(
            UUID(organization_id), UUID(employee_id), current_magi, threshold
        )
    )


@app.task
def send_write_back_confirmation(
    organization_id: str,
    batch_summary: dict,
):
    """Confirm successful write-back to payroll system."""
    records_count = batch_summary.get("completed_records", 0)
    provider = batch_summary.get("provider", "payroll system")
    logger.info(
        f"Write-back confirmed: org={organization_id}, records={records_count}"
    )
    _run_async(
        _async_send_writeback_confirmation(
            UUID(organization_id), records_count, provider
        )
    )


# ── Async implementation helpers ─────────────────────


async def _async_send_approval_reminder(org_id: UUID, run_id: str):
    """Send approval reminder email."""
    from backend.services.email import send_approval_reminder_email

    email, org_name = await _get_org_contact(org_id)
    if not email:
        logger.warning(f"No contact email for org {org_id}, skipping approval reminder")
        return

    send_approval_reminder_email(
        to_email=email,
        org_name=org_name,
        run_id=run_id,
        period="Current Period",
    )


async def _async_send_sync_alert(org_id: UUID, integration_id: UUID, error_message: str):
    """Send sync failure alert email."""
    from backend.services.email import send_sync_failure_email

    email, org_name = await _get_org_contact(org_id)
    if not email:
        logger.warning(f"No contact email for org {org_id}, skipping sync alert")
        return

    provider = await _get_integration_provider(integration_id)
    send_sync_failure_email(
        to_email=email,
        org_name=org_name,
        provider=provider,
        error_message=error_message,
    )


async def _async_send_anomaly_alert(
    org_id: UUID, employee_id: UUID, anomaly_type: str, details: str,
):
    """Send anomaly alert email."""
    from backend.services.email import send_anomaly_alert_email

    email, org_name = await _get_org_contact(org_id)
    if not email:
        logger.warning(f"No contact email for org {org_id}, skipping anomaly alert")
        return

    employee_name = await _get_employee_name(employee_id)
    send_anomaly_alert_email(
        to_email=email,
        org_name=org_name,
        employee_name=employee_name,
        anomaly_type=anomaly_type,
        details=details,
    )


async def _async_send_phase_out_warning(
    org_id: UUID, employee_id: UUID, current_magi: str, threshold: str,
):
    """Send phase-out warning email."""
    from backend.services.email import send_phase_out_warning_email

    email, org_name = await _get_org_contact(org_id)
    if not email:
        logger.warning(f"No contact email for org {org_id}, skipping phase-out warning")
        return

    employee_name = await _get_employee_name(employee_id)
    send_phase_out_warning_email(
        to_email=email,
        org_name=org_name,
        employee_name=employee_name,
        current_magi=current_magi,
        threshold=threshold,
    )


async def _async_send_writeback_confirmation(
    org_id: UUID, records_count: int, provider: str,
):
    """Send write-back confirmation email."""
    from backend.services.email import send_writeback_confirmation_email

    email, org_name = await _get_org_contact(org_id)
    if not email:
        logger.warning(f"No contact email for org {org_id}, skipping writeback confirmation")
        return

    send_writeback_confirmation_email(
        to_email=email,
        org_name=org_name,
        records_count=records_count,
        provider=provider,
    )
