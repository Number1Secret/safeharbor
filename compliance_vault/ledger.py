"""
Compliance Vault Ledger

Append-only ledger with cryptographic hash chain.
Each entry links to the previous via SHA-256, creating
an immutable audit trail.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# IRS retention requirement
RETENTION_YEARS = 7


class ComplianceVaultLedger:
    """
    Append-only ledger with hash chain integrity.

    Each entry contains:
    - entry_hash: SHA-256 of (previous_hash + content + timestamp)
    - previous_hash: Hash of the preceding entry
    - sequence_number: Monotonically increasing counter
    - content: JSON payload of the event
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(
        self,
        organization_id: UUID,
        entry_type: str,
        content: dict[str, Any],
        actor_id: UUID | None = None,
        actor_type: str | None = None,
    ) -> dict:
        """
        Append a new entry to the vault.

        Args:
            organization_id: Organization this entry belongs to
            entry_type: Type of entry (calculation, write_back, classification, etc.)
            content: JSON-serializable content
            actor_id: Who performed the action
            actor_type: Type of actor (user, system, api)

        Returns:
            Created vault entry as dict
        """
        from backend.models.compliance_vault import ComplianceVault

        # Get the latest entry for hash chaining
        prev = await self._get_latest_entry(organization_id)
        previous_hash = prev.entry_hash if prev else "GENESIS"
        next_sequence = (prev.sequence_number + 1) if prev else 1

        # Serialize content deterministically
        content_json = json.dumps(content, sort_keys=True, default=str)

        # Calculate entry hash
        now = datetime.utcnow()
        hash_input = f"{previous_hash}|{content_json}|{now.isoformat()}"
        entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Calculate retention expiry
        retention_expires = now + timedelta(days=RETENTION_YEARS * 365)

        # Create entry
        entry = ComplianceVault(
            id=uuid4(),
            organization_id=organization_id,
            entry_type=entry_type,
            entry_hash=entry_hash,
            previous_hash=previous_hash if prev else None,
            sequence_number=next_sequence,
            content=content,
            content_hash=hashlib.sha256(content_json.encode()).hexdigest(),
            retention_expires_at=retention_expires,
            actor_id=actor_id,
            actor_type=actor_type or "system",
        )

        self.db.add(entry)
        await self.db.flush()

        logger.info(
            f"Vault entry #{next_sequence} created: "
            f"type={entry_type}, hash={entry_hash[:16]}..."
        )

        return {
            "id": str(entry.id),
            "entry_type": entry_type,
            "entry_hash": entry_hash,
            "previous_hash": previous_hash,
            "sequence_number": next_sequence,
            "created_at": now.isoformat(),
        }

    async def append_calculation(
        self,
        organization_id: UUID,
        calculation_run_id: UUID,
        employee_id: UUID,
        calculation_data: dict,
        actor_id: UUID | None = None,
    ) -> dict:
        """Convenience method for calculation entries."""
        return await self.append(
            organization_id=organization_id,
            entry_type="calculation",
            content={
                "action": "calculation_completed",
                "calculation_run_id": str(calculation_run_id),
                "employee_id": str(employee_id),
                **calculation_data,
            },
            actor_id=actor_id,
        )

    async def append_classification(
        self,
        organization_id: UUID,
        employee_id: UUID,
        classification_data: dict,
        actor_id: UUID | None = None,
    ) -> dict:
        """Convenience method for TTOC classification entries."""
        return await self.append(
            organization_id=organization_id,
            entry_type="classification",
            content={
                "action": "ttoc_classification",
                "employee_id": str(employee_id),
                **classification_data,
            },
            actor_id=actor_id,
        )

    async def append_approval(
        self,
        organization_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_id: UUID,
        details: dict | None = None,
    ) -> dict:
        """Convenience method for approval/rejection entries."""
        return await self.append(
            organization_id=organization_id,
            entry_type="approval",
            content={
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "details": details or {},
            },
            actor_id=actor_id,
            actor_type="user",
        )

    async def get_entry(
        self,
        entry_id: UUID,
    ) -> dict | None:
        """Get a single vault entry by ID."""
        from backend.models.compliance_vault import ComplianceVault

        result = await self.db.execute(
            select(ComplianceVault).where(ComplianceVault.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None

        return self._entry_to_dict(entry)

    async def get_entries(
        self,
        organization_id: UUID,
        entry_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get vault entries with optional type filter."""
        from backend.models.compliance_vault import ComplianceVault

        query = select(ComplianceVault).where(
            ComplianceVault.organization_id == organization_id
        )
        if entry_type:
            query = query.where(ComplianceVault.entry_type == entry_type)

        query = query.order_by(ComplianceVault.sequence_number.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        entries = result.scalars().all()

        return [self._entry_to_dict(e) for e in entries]

    async def get_entry_count(
        self,
        organization_id: UUID,
    ) -> int:
        """Get total entry count for an organization."""
        from backend.models.compliance_vault import ComplianceVault

        result = await self.db.execute(
            select(func.count(ComplianceVault.id)).where(
                ComplianceVault.organization_id == organization_id
            )
        )
        return result.scalar() or 0

    async def _get_latest_entry(self, organization_id: UUID):
        """Get the most recent vault entry for hash chaining."""
        from backend.models.compliance_vault import ComplianceVault

        result = await self.db.execute(
            select(ComplianceVault)
            .where(ComplianceVault.organization_id == organization_id)
            .order_by(ComplianceVault.sequence_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _entry_to_dict(self, entry) -> dict:
        """Convert a vault entry model to dict."""
        return {
            "id": str(entry.id),
            "organization_id": str(entry.organization_id),
            "entry_type": entry.entry_type,
            "entry_hash": entry.entry_hash,
            "previous_hash": entry.previous_hash,
            "sequence_number": entry.sequence_number,
            "content": entry.content,
            "content_hash": entry.content_hash,
            "retention_expires_at": entry.retention_expires_at.isoformat()
            if entry.retention_expires_at else None,
            "actor_id": str(entry.actor_id) if entry.actor_id else None,
            "actor_type": entry.actor_type,
            "created_at": entry.created_at.isoformat(),
        }
