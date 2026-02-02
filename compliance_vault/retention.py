"""
Compliance Vault Retention

Manages the 7-year retention policy for vault entries.
Handles expiry processing and archival.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def process_expired_entries(
    db: AsyncSession,
    dry_run: bool = True,
) -> dict:
    """
    Process expired vault entries.

    By default runs in dry-run mode to preview what would be deleted.
    Entries past their retention_expires_at are eligible for removal.

    Args:
        db: Database session
        dry_run: If True, only count without deleting

    Returns:
        Dict with counts and status
    """
    from backend.models.compliance_vault import ComplianceVault

    now = datetime.utcnow()

    # Count expired entries
    count_result = await db.execute(
        select(func.count(ComplianceVault.id)).where(
            ComplianceVault.retention_expires_at <= now
        )
    )
    expired_count = count_result.scalar() or 0

    if expired_count == 0:
        return {
            "expired_count": 0,
            "deleted_count": 0,
            "dry_run": dry_run,
            "message": "No expired entries found",
        }

    if dry_run:
        return {
            "expired_count": expired_count,
            "deleted_count": 0,
            "dry_run": True,
            "message": f"{expired_count} entries eligible for deletion (dry run)",
        }

    # Archive before deletion
    await _archive_expired_entries(db, now)

    # Delete expired entries
    await db.execute(
        delete(ComplianceVault).where(
            ComplianceVault.retention_expires_at <= now
        )
    )
    await db.flush()

    logger.info(f"Deleted {expired_count} expired vault entries")

    return {
        "expired_count": expired_count,
        "deleted_count": expired_count,
        "dry_run": False,
        "message": f"Deleted {expired_count} expired entries",
    }


async def get_retention_summary(
    db: AsyncSession,
    organization_id: UUID | None = None,
) -> dict:
    """
    Get summary of vault entry retention status.

    Returns counts of entries by retention status.
    """
    from backend.models.compliance_vault import ComplianceVault

    now = datetime.utcnow()
    query = select(ComplianceVault)

    if organization_id:
        query = query.where(ComplianceVault.organization_id == organization_id)

    # Total entries
    total_result = await db.execute(
        select(func.count(ComplianceVault.id)).where(
            *(
                [ComplianceVault.organization_id == organization_id]
                if organization_id else []
            )
        )
    )
    total = total_result.scalar() or 0

    # Expired entries
    expired_result = await db.execute(
        select(func.count(ComplianceVault.id)).where(
            ComplianceVault.retention_expires_at <= now,
            *(
                [ComplianceVault.organization_id == organization_id]
                if organization_id else []
            ),
        )
    )
    expired = expired_result.scalar() or 0

    # Expiring within 1 year
    from datetime import timedelta
    one_year = now + timedelta(days=365)
    expiring_soon_result = await db.execute(
        select(func.count(ComplianceVault.id)).where(
            ComplianceVault.retention_expires_at > now,
            ComplianceVault.retention_expires_at <= one_year,
            *(
                [ComplianceVault.organization_id == organization_id]
                if organization_id else []
            ),
        )
    )
    expiring_soon = expiring_soon_result.scalar() or 0

    return {
        "total_entries": total,
        "expired": expired,
        "expiring_within_year": expiring_soon,
        "active": total - expired,
    }


async def _archive_expired_entries(
    db: AsyncSession,
    before: datetime,
):
    """Archive expired entries before deletion (future: S3/GCS export)."""
    logger.info(f"Archiving entries expired before {before.isoformat()}")
    # In production, this would export to cold storage (S3, GCS)
    # before deletion. For now, just log the action.
    pass
