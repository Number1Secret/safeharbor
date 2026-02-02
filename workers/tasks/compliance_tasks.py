"""
Compliance Tasks

Background tasks for compliance vault maintenance and audit operations.
"""

import asyncio
import logging

from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task
def vault_maintenance():
    """
    Daily vault maintenance.

    - Check hash chain integrity
    - Process expired entries
    - Generate retention reports
    """
    logger.info("Starting vault maintenance")
    asyncio.get_event_loop().run_until_complete(_async_vault_maintenance())


@app.task
def verify_vault_integrity(organization_id: str):
    """Verify vault integrity for a specific organization."""
    from uuid import UUID
    logger.info(f"Verifying vault for org {organization_id}")
    asyncio.get_event_loop().run_until_complete(
        _async_verify_org(UUID(organization_id))
    )


@app.task
def generate_audit_pack_async(
    organization_id: str,
    tax_year: int,
):
    """Generate audit pack in background."""
    from uuid import UUID
    logger.info(f"Generating audit pack for org {organization_id}, year {tax_year}")
    result = asyncio.get_event_loop().run_until_complete(
        _async_generate_pack(UUID(organization_id), tax_year)
    )
    return result


async def _async_vault_maintenance():
    """Run all vault maintenance operations."""
    from backend.db.session import get_async_session
    from sqlalchemy import select
    from backend.models.organization import Organization
    from compliance_vault.integrity import verify_chain
    from compliance_vault.retention import process_expired_entries, get_retention_summary

    async with get_async_session() as db:
        # Get all organizations
        result = await db.execute(select(Organization))
        orgs = result.scalars().all()

        for org in orgs:
            # Verify integrity
            integrity = await verify_chain(db, org.id)
            if not integrity["is_valid"]:
                logger.error(
                    f"VAULT INTEGRITY FAILURE for org {org.id}: "
                    f"{integrity['message']}"
                )
                # TODO: Send alert notification
            else:
                logger.info(
                    f"Vault OK for org {org.id}: "
                    f"{integrity['entries_checked']} entries verified"
                )

            # Check retention
            retention = await get_retention_summary(db, org.id)
            if retention["expired"] > 0:
                logger.info(
                    f"Org {org.id}: {retention['expired']} entries eligible for cleanup"
                )

        # Process expired entries (dry run by default)
        expired_result = await process_expired_entries(db, dry_run=True)
        logger.info(f"Retention check: {expired_result['message']}")


async def _async_verify_org(organization_id):
    """Verify vault for a single organization."""
    from backend.db.session import get_async_session
    from compliance_vault.integrity import verify_chain

    async with get_async_session() as db:
        result = await verify_chain(db, organization_id)
        if result["is_valid"]:
            logger.info(
                f"Vault integrity verified for org {organization_id}: "
                f"{result['entries_checked']} entries"
            )
        else:
            logger.error(
                f"Vault integrity FAILED for org {organization_id}: "
                f"{result['message']}"
            )
        return result


async def _async_generate_pack(organization_id, tax_year):
    """Generate audit pack asynchronously."""
    from backend.db.session import get_async_session
    from compliance_vault.export import generate_audit_pack

    async with get_async_session() as db:
        pack = await generate_audit_pack(
            db=db,
            organization_id=organization_id,
            tax_year=tax_year,
        )
        logger.info(
            f"Audit pack generated for org {organization_id}: "
            f"{len(pack.get('sections', []))} sections"
        )
        return pack
