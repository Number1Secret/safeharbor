"""
Integration Model

OAuth connections to external systems (Payroll, POS, Timekeeping, HRIS).
Tracks token lifecycle and sync status.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.organization import Organization


class IntegrationProvider(str, Enum):
    """Supported integration providers per PRD Section 3.2.1."""

    # Payroll
    ADP = "adp"
    GUSTO = "gusto"
    PAYCHEX = "paychex"
    QUICKBOOKS = "quickbooks"

    # Point of Sale
    TOAST = "toast"
    SQUARE = "square"
    CLOVER = "clover"

    # Timekeeping
    DEPUTY = "deputy"
    WHEN_I_WORK = "when_i_work"
    HOMEBASE = "homebase"

    # HRIS
    BAMBOOHR = "bamboohr"
    RIPPLING = "rippling"
    ZENEFITS = "zenefits"


class IntegrationCategory(str, Enum):
    """Categories of integrations."""

    PAYROLL = "payroll"
    POS = "pos"
    TIMEKEEPING = "timekeeping"
    HRIS = "hris"


class IntegrationStatus(str, Enum):
    """Connection status."""

    CONNECTED = "connected"  # Active and working
    EXPIRED = "expired"  # Token expired, needs refresh
    REVOKED = "revoked"  # Access revoked by user
    ERROR = "error"  # Connection error
    PENDING = "pending"  # OAuth flow in progress


# Provider to category mapping
PROVIDER_CATEGORIES = {
    IntegrationProvider.ADP: IntegrationCategory.PAYROLL,
    IntegrationProvider.GUSTO: IntegrationCategory.PAYROLL,
    IntegrationProvider.PAYCHEX: IntegrationCategory.PAYROLL,
    IntegrationProvider.QUICKBOOKS: IntegrationCategory.PAYROLL,
    IntegrationProvider.TOAST: IntegrationCategory.POS,
    IntegrationProvider.SQUARE: IntegrationCategory.POS,
    IntegrationProvider.CLOVER: IntegrationCategory.POS,
    IntegrationProvider.DEPUTY: IntegrationCategory.TIMEKEEPING,
    IntegrationProvider.WHEN_I_WORK: IntegrationCategory.TIMEKEEPING,
    IntegrationProvider.HOMEBASE: IntegrationCategory.TIMEKEEPING,
    IntegrationProvider.BAMBOOHR: IntegrationCategory.HRIS,
    IntegrationProvider.RIPPLING: IntegrationCategory.HRIS,
    IntegrationProvider.ZENEFITS: IntegrationCategory.HRIS,
}


class Integration(TimestampMixin, Base):
    """
    OAuth connection to external systems.

    Manages OAuth tokens (encrypted at rest), tracks sync status,
    and stores provider-specific configuration.
    """

    __tablename__ = "integrations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Provider identification
    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Integration provider: adp|gusto|toast|square|etc.",
    )
    provider_category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Provider category: payroll|pos|timekeeping|hris",
    )

    # Display name (user-provided or default)
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User-friendly name for this connection",
    )

    # OAuth tokens (encrypted at rest using Fernet)
    access_token_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="Fernet-encrypted OAuth access token",
    )
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="Fernet-encrypted OAuth refresh token",
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Token expiration timestamp",
    )

    # OAuth metadata
    oauth_state: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="OAuth state parameter for CSRF protection",
    )
    scopes: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Granted OAuth scopes",
    )

    # Connection status
    status: Mapped[str] = mapped_column(
        String(20),
        default=IntegrationStatus.PENDING.value,
        nullable=False,
        comment="Connection status: connected|expired|revoked|error|pending",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message if status is 'error'",
    )
    error_count: Mapped[int] = mapped_column(
        default=0,
        comment="Consecutive error count for circuit breaker",
    )

    # Sync tracking
    last_sync_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Timestamp of last successful sync",
    )
    last_sync_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Status of last sync: success|partial|failed",
    )
    last_sync_records: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Number of records synced in last sync",
    )
    sync_cursor: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Pagination/cursor state for incremental sync",
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Scheduled next sync time",
    )

    # Webhooks (if supported by provider)
    webhook_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Webhook registration ID at provider",
    )
    webhook_secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Webhook signing secret",
    )
    webhook_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Our webhook endpoint URL",
    )

    # Provider-specific configuration
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Provider-specific configuration (e.g., restaurant_guid for Toast)",
    )

    # Provider-specific metadata (from OAuth response)
    provider_metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Metadata from provider (company name, account ID, etc.)",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        back_populates="integrations",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_org_provider",
        ),
        Index("ix_integrations_organization_id", "organization_id"),
        Index("ix_integrations_provider", "provider"),
        Index("ix_integrations_status", "status"),
        Index("ix_integrations_next_sync", "next_sync_at"),
    )

    def __repr__(self) -> str:
        return f"<Integration {self.provider} ({self.status}) for org={self.organization_id}>"

    @property
    def is_connected(self) -> bool:
        """Check if integration is actively connected."""
        return self.status == IntegrationStatus.CONNECTED.value

    @property
    def needs_token_refresh(self) -> bool:
        """Check if token needs refresh (within 5 minutes of expiry)."""
        if not self.token_expires_at:
            return False
        from datetime import timedelta

        return datetime.utcnow() + timedelta(minutes=5) >= self.token_expires_at

    @property
    def can_sync(self) -> bool:
        """Check if integration can be synced."""
        return self.is_connected and self.access_token_encrypted is not None
