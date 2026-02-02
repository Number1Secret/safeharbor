"""
User Model

Authentication and authorization for SafeHarbor users.
Supports password-based login, SSO, and invite flows.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.organization import Organization


class User(TimestampMixin, Base):
    """
    User record for authentication and authorization.

    Each user belongs to one organization and has a role that determines
    their permissions (see backend/middleware/rbac.py for role definitions).
    """

    __tablename__ = "users"

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

    # Identity
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Authentication
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Nullable for SSO-only users",
    )

    # Authorization
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="viewer",
        comment="Role: owner, admin, manager, viewer",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Email verified or SSO authenticated",
    )

    # Login tracking
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Invite flow
    invite_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    invite_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # SSO
    sso_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="SSO provider name (e.g., okta, azure_ad)",
    )
    sso_external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="External user ID from SSO provider",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        back_populates="users",
    )

    __table_args__ = (
        Index("ix_users_org_role", "organization_id", "role"),
        Index("ix_users_sso", "sso_provider", "sso_external_id"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"
