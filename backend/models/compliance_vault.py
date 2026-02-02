"""
ComplianceVault Model

Immutable audit ledger with hash chain integrity.
7-year retention policy for IRS compliance.
"""

from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class VaultEntryType(str, Enum):
    """Types of vault entries."""

    # Calculation events
    CALCULATION_FINALIZED = "calculation_finalized"
    CALCULATION_CORRECTED = "calculation_corrected"

    # Employee events
    EMPLOYEE_CREATED = "employee_created"
    EMPLOYEE_UPDATED = "employee_updated"
    EMPLOYEE_TERMINATED = "employee_terminated"

    # Classification events
    TTOC_CLASSIFIED = "ttoc_classified"
    TTOC_OVERRIDDEN = "ttoc_overridden"
    TTOC_VERIFIED = "ttoc_verified"

    # Integration events
    INTEGRATION_SYNC = "integration_sync"
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"

    # Configuration events
    CONFIG_CHANGED = "config_changed"
    SETTINGS_UPDATED = "settings_updated"

    # Approval events
    APPROVAL_SUBMITTED = "approval_submitted"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    # Export events
    AUDIT_PACK_GENERATED = "audit_pack_generated"
    W2_EXPORT_GENERATED = "w2_export_generated"


class ActorType(str, Enum):
    """Type of actor that created the vault entry."""

    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"
    CALCULATION_ENGINE = "calculation_engine"


class ComplianceVault(Base):
    """
    Immutable audit ledger with hash chain integrity.

    Every significant action in SafeHarbor is recorded here with:
    - Cryptographic hash of the entry content
    - Link to previous entry (hash chain)
    - Full snapshot of relevant state
    - 7-year retention per IRS requirements

    This table is append-only. No UPDATE or DELETE operations
    should ever be performed on vault entries.
    """

    __tablename__ = "compliance_vault"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    # Hash chain for integrity verification
    entry_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="SHA-256 hash of entry content (JSON-serialized)",
    )
    previous_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Hash of previous entry in chain (null for genesis)",
    )
    sequence_number: Mapped[int] = mapped_column(
        nullable=False,
        comment="Monotonically increasing sequence number per organization",
    )

    # Entry metadata
    entry_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of vault entry",
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Organization this entry belongs to (RESTRICT prevents deletion)",
    )

    # Related entities (optional, for querying)
    employee_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="Related employee if applicable",
    )
    calculation_run_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="Related calculation run if applicable",
    )

    # Immutable content - full snapshot of state
    content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full snapshot of state at this point",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of content JSON for tamper detection",
    )

    # Summary for quick querying (derived from content)
    summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Human-readable summary of the entry",
    )

    # Timestamp (no updated_at - immutable)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Timestamp when entry was created",
    )

    # Retention tracking (7 years per PRD)
    retention_expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Entry can be deleted after this date (7 years from creation)",
    )

    # Actor tracking
    actor_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User/system ID that triggered this entry",
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        default=ActorType.SYSTEM.value,
        nullable=False,
        comment="Type of actor: user|system|integration|calculation_engine",
    )
    actor_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of actor (for user-initiated actions)",
    )

    # Verification metadata
    verified_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last time this entry was verified in integrity check",
    )
    verification_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Result of last verification: valid|invalid|pending",
    )

    __table_args__ = (
        CheckConstraint(
            "entry_hash ~ '^[a-f0-9]{64}$'",
            name="valid_entry_hash",
        ),
        CheckConstraint(
            "previous_hash IS NULL OR previous_hash ~ '^[a-f0-9]{64}$'",
            name="valid_previous_hash",
        ),
        CheckConstraint(
            "retention_expires_at > created_at",
            name="valid_retention_date",
        ),
        Index("ix_compliance_vault_org_id", "organization_id"),
        Index("ix_compliance_vault_entry_type", "entry_type"),
        Index("ix_compliance_vault_created_at", "created_at"),
        Index("ix_compliance_vault_employee_id", "employee_id"),
        Index("ix_compliance_vault_calculation_run_id", "calculation_run_id"),
        Index("ix_compliance_vault_retention", "retention_expires_at"),
        Index("ix_compliance_vault_org_sequence", "organization_id", "sequence_number"),
    )

    def __repr__(self) -> str:
        return f"<ComplianceVault {self.entry_type} seq={self.sequence_number} org={self.organization_id}>"

    @classmethod
    def calculate_retention_date(cls, created_at: datetime | None = None) -> datetime:
        """Calculate retention expiration date (7 years from creation)."""
        base = created_at or datetime.utcnow()
        return base + timedelta(days=7 * 365)

    @property
    def is_genesis(self) -> bool:
        """Check if this is the first entry in the chain (no previous hash)."""
        return self.previous_hash is None

    @property
    def can_expire(self) -> bool:
        """Check if this entry has passed its retention period."""
        return datetime.utcnow() >= self.retention_expires_at
