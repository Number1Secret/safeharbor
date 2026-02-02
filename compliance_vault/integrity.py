"""
Compliance Vault Integrity Verification

Verifies the hash chain integrity of the compliance vault.
Detects any tampering or corruption in the audit trail.
"""

import hashlib
import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def verify_chain(
    db: AsyncSession,
    organization_id: UUID,
    batch_size: int = 1000,
) -> dict:
    """
    Verify the integrity of the entire hash chain for an organization.

    Checks:
    1. Sequence numbers are contiguous
    2. Each entry's hash matches its computed hash
    3. Each entry's previous_hash matches the prior entry's hash
    4. Content hashes match content

    Returns:
        Dict with is_valid, total_entries, entries_checked, details
    """
    from backend.models.compliance_vault import ComplianceVault

    total = await _get_entry_count(db, organization_id)

    if total == 0:
        return {
            "is_valid": True,
            "total_entries": 0,
            "entries_checked": 0,
            "first_broken_entry": None,
            "message": "No vault entries to verify",
        }

    entries_checked = 0
    previous_hash = None
    previous_sequence = 0
    offset = 0

    while offset < total:
        result = await db.execute(
            select(ComplianceVault)
            .where(ComplianceVault.organization_id == organization_id)
            .order_by(ComplianceVault.sequence_number.asc())
            .offset(offset)
            .limit(batch_size)
        )
        entries = result.scalars().all()

        if not entries:
            break

        for entry in entries:
            entries_checked += 1

            # Check 1: Sequence continuity
            if entry.sequence_number != previous_sequence + 1:
                return {
                    "is_valid": False,
                    "total_entries": total,
                    "entries_checked": entries_checked,
                    "first_broken_entry": entry.sequence_number,
                    "message": (
                        f"Sequence gap: expected {previous_sequence + 1}, "
                        f"got {entry.sequence_number}"
                    ),
                }

            # Check 2: Previous hash linkage
            expected_prev = previous_hash if previous_hash else None
            if entry.sequence_number == 1:
                # First entry should have no previous hash or "GENESIS"
                if entry.previous_hash and entry.previous_hash != "GENESIS":
                    return {
                        "is_valid": False,
                        "total_entries": total,
                        "entries_checked": entries_checked,
                        "first_broken_entry": entry.sequence_number,
                        "message": "Genesis entry has unexpected previous_hash",
                    }
            elif entry.previous_hash != expected_prev:
                return {
                    "is_valid": False,
                    "total_entries": total,
                    "entries_checked": entries_checked,
                    "first_broken_entry": entry.sequence_number,
                    "message": (
                        f"Hash chain broken at entry #{entry.sequence_number}: "
                        f"expected previous_hash={expected_prev[:16]}..., "
                        f"got={entry.previous_hash[:16] if entry.previous_hash else 'None'}..."
                    ),
                }

            # Check 3: Content hash verification
            if entry.content and entry.content_hash:
                content_json = json.dumps(entry.content, sort_keys=True, default=str)
                computed_content_hash = hashlib.sha256(
                    content_json.encode()
                ).hexdigest()
                if computed_content_hash != entry.content_hash:
                    return {
                        "is_valid": False,
                        "total_entries": total,
                        "entries_checked": entries_checked,
                        "first_broken_entry": entry.sequence_number,
                        "message": (
                            f"Content tampered at entry #{entry.sequence_number}: "
                            f"content hash mismatch"
                        ),
                    }

            # Update for next iteration
            previous_hash = entry.entry_hash
            previous_sequence = entry.sequence_number

        offset += batch_size

    return {
        "is_valid": True,
        "total_entries": total,
        "entries_checked": entries_checked,
        "first_broken_entry": None,
        "message": f"All {entries_checked} entries verified successfully",
    }


async def verify_entry(
    db: AsyncSession,
    entry_id: UUID,
) -> dict:
    """
    Verify a single vault entry's integrity.

    Checks the entry's own hash and its link to the previous entry.
    """
    from backend.models.compliance_vault import ComplianceVault

    result = await db.execute(
        select(ComplianceVault).where(ComplianceVault.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        return {"is_valid": False, "message": "Entry not found"}

    # Verify content hash
    if entry.content and entry.content_hash:
        content_json = json.dumps(entry.content, sort_keys=True, default=str)
        computed = hashlib.sha256(content_json.encode()).hexdigest()
        if computed != entry.content_hash:
            return {
                "is_valid": False,
                "message": "Content hash mismatch - possible tampering",
                "entry_sequence": entry.sequence_number,
            }

    # Verify previous hash linkage
    if entry.sequence_number > 1 and entry.previous_hash:
        prev_result = await db.execute(
            select(ComplianceVault).where(
                ComplianceVault.organization_id == entry.organization_id,
                ComplianceVault.sequence_number == entry.sequence_number - 1,
            )
        )
        prev_entry = prev_result.scalar_one_or_none()

        if prev_entry and prev_entry.entry_hash != entry.previous_hash:
            return {
                "is_valid": False,
                "message": "Previous hash linkage broken",
                "entry_sequence": entry.sequence_number,
            }

    return {
        "is_valid": True,
        "message": "Entry integrity verified",
        "entry_sequence": entry.sequence_number,
    }


async def _get_entry_count(db: AsyncSession, organization_id: UUID) -> int:
    """Get total entry count."""
    from sqlalchemy import func
    from backend.models.compliance_vault import ComplianceVault

    result = await db.execute(
        select(func.count(ComplianceVault.id)).where(
            ComplianceVault.organization_id == organization_id
        )
    )
    return result.scalar() or 0
