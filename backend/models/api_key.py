"""
API Key Model

Programmatic access keys for SafeHarbor API.
Keys are hashed with SHA-256 before storage; the raw key is shown only once at creation.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class APIKey(TimestampMixin, Base):
    """
    API key for programmatic access.

    The raw key is prefixed with 'sh_' and shown only once at creation.
    We store a SHA-256 hash for validation. The key_prefix (first 12 chars)
    is stored for display purposes.
    """

    __tablename__ = "api_keys"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    # Organization
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Creator
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this API key",
    )

    # Key identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name for the key",
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="SHA-256 hash of the full API key",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="First 12 chars of key for display (e.g., sh_abc123...)",
    )

    # Permissions
    permissions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of permission strings granted to this key",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Key expiration time; null = never expires",
    )

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_api_keys_org_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<APIKey {self.key_prefix} name={self.name}>"
