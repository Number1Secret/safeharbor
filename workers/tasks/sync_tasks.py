"""
Sync Tasks

Background tasks for syncing data from external integrations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID

from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_integration(self, integration_id: str):
    """
    Sync a single integration.

    Fetches latest data from the provider and stores in database.
    """
    logger.info(f"Starting sync for integration {integration_id}")
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _async_sync_integration(UUID(integration_id))
        )
        logger.info(
            f"Sync completed for {integration_id}: "
            f"{result.get('records_fetched', 0)} records fetched"
        )
        return result
    except Exception as exc:
        logger.error(f"Sync failed for {integration_id}: {exc}")
        raise self.retry(exc=exc)


@app.task
def sync_all_payroll():
    """Sync all active payroll integrations."""
    logger.info("Starting payroll sync for all organizations")
    asyncio.get_event_loop().run_until_complete(_async_sync_by_category("payroll"))


@app.task
def sync_all_pos():
    """Sync all active POS integrations."""
    logger.info("Starting POS sync for all organizations")
    asyncio.get_event_loop().run_until_complete(_async_sync_by_category("pos"))


@app.task
def sync_all_timekeeping():
    """Sync all active timekeeping integrations."""
    logger.info("Starting timekeeping sync for all organizations")
    asyncio.get_event_loop().run_until_complete(_async_sync_by_category("timekeeping"))


@app.task
def check_stale_integrations():
    """Check for integrations that haven't synced recently."""
    logger.info("Checking for stale integrations")
    asyncio.get_event_loop().run_until_complete(_async_check_stale())


async def _async_sync_integration(integration_id: UUID) -> dict:
    """Async implementation of integration sync."""
    from backend.db.session import get_async_session
    from sqlalchemy import select, update
    from backend.models.integration import Integration
    from backend.config import get_settings
    from integrations.oauth_manager import OAuthTokenManager

    async with get_async_session() as db:
        # Get integration record
        result = await db.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        if not integration:
            return {"error": "Integration not found"}

        if not integration.is_connected:
            return {"error": "Integration is inactive"}

        # Update sync status
        integration.last_sync_status = "syncing"
        integration.last_sync_at = datetime.utcnow()
        await db.commit()

        try:
            # Decrypt tokens and create client
            settings = get_settings()
            token_manager = OAuthTokenManager(settings.encryption_key)

            access_token, refresh_token = token_manager.decrypt_tokens(
                integration.access_token_encrypted,
                integration.refresh_token_encrypted,
            )

            # Check if token needs refresh
            if token_manager.needs_refresh(integration.token_expires_at):
                client = _create_client(
                    integration.provider, access_token, refresh_token,
                    integration.provider_metadata or {},
                )
                new_access, new_refresh, expires_in = await client.refresh_access_token()
                enc_access, enc_refresh = token_manager.encrypt_tokens(
                    new_access, new_refresh
                )
                integration.access_token_encrypted = enc_access
                integration.refresh_token_encrypted = enc_refresh
                if expires_in:
                    integration.token_expires_at = (
                        datetime.utcnow() + timedelta(seconds=expires_in)
                    )
                access_token = new_access
                await client.close()

            # Create integration client
            client = _create_client(
                integration.provider, access_token, refresh_token,
                integration.provider_metadata or {},
            )

            # Sync employees
            sync_result = await client.sync_employees(
                since=integration.sync_cursor.get("last_employee_sync")
                if integration.sync_cursor else None
            )

            # Update sync cursor
            cursor = integration.sync_cursor or {}
            cursor["last_employee_sync"] = datetime.utcnow().isoformat()
            integration.sync_cursor = cursor
            integration.last_sync_status = "success" if sync_result.success else "failed"

            await client.close()
            await db.commit()

            return {
                "success": sync_result.success,
                "records_fetched": sync_result.records_fetched,
                "records_created": sync_result.records_created,
                "errors": sync_result.errors,
            }

        except Exception as e:
            integration.last_sync_status = "failed"
            await db.commit()
            raise


async def _async_sync_by_category(category: str):
    """Sync all integrations of a given category."""
    from backend.db.session import get_async_session
    from sqlalchemy import select
    from backend.models.integration import Integration

    async with get_async_session() as db:
        result = await db.execute(
            select(Integration.id).where(
                Integration.provider_category == category,
                Integration.status == "connected",
            )
        )
        integration_ids = result.scalars().all()

    for int_id in integration_ids:
        sync_integration.delay(str(int_id))


async def _async_check_stale():
    """Check for integrations that are overdue for sync."""
    from backend.db.session import get_async_session
    from sqlalchemy import select, or_
    from backend.models.integration import Integration

    stale_threshold = datetime.utcnow() - timedelta(hours=2)

    async with get_async_session() as db:
        result = await db.execute(
            select(Integration).where(
                Integration.status == "connected",
                or_(
                    Integration.last_sync_at < stale_threshold,
                    Integration.last_sync_at.is_(None),
                ),
            )
        )
        stale = result.scalars().all()

        for integration in stale:
            logger.warning(
                f"Stale integration: {integration.provider} "
                f"(org={integration.organization_id}, "
                f"last_sync={integration.last_sync_at})"
            )
            # Trigger a sync
            sync_integration.delay(str(integration.id))


def _create_client(provider: str, access_token: str, refresh_token: str | None, config: dict):
    """Factory for creating integration clients."""
    from integrations.payroll.adp import ADPIntegration
    from integrations.payroll.gusto import GustoIntegration
    from integrations.payroll.paychex import PaychexIntegration
    from integrations.payroll.quickbooks_payroll import QuickBooksPayrollIntegration
    from integrations.pos.toast import ToastIntegration

    clients = {
        "adp": ADPIntegration,
        "gusto": GustoIntegration,
        "paychex": PaychexIntegration,
        "quickbooks": QuickBooksPayrollIntegration,
        "toast": ToastIntegration,
    }

    cls = clients.get(provider)
    if not cls:
        raise ValueError(f"Unknown provider: {provider}")
    return cls(access_token=access_token, refresh_token=refresh_token, config=config)
