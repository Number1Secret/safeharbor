"""
Organization Model

Multi-tenant root entity for SafeHarbor AI.
All tax compliance data is scoped to an organization.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.calculation_run import CalculationRun
    from backend.models.employee import Employee
    from backend.models.integration import Integration
    from backend.models.user import User


class OrganizationTier(str, Enum):
    """Subscription tier levels per PRD Section 8.1."""

    STARTER = "starter"  # $99/month flat, up to 50 employees
    PROFESSIONAL = "pro"  # $4/employee/month, 50-500 employees
    ENTERPRISE = "enterprise"  # $3/employee/month + $500/mo, 500+ employees


class OrganizationStatus(str, Enum):
    """Organization account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Organization(TimestampMixin, Base):
    """
    Multi-tenant organization record.

    Root entity for all tax compliance data. Each employer using SafeHarbor
    is represented as an Organization with their own employees, integrations,
    and calculation history.
    """

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Legal business name",
    )
    ein: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        unique=True,
        comment="Employer Identification Number (XX-XXXXXXX format)",
    )
    tax_year: Mapped[int] = mapped_column(
        nullable=False,
        default=2025,
        comment="Current tax year for calculations",
    )

    # Subscription
    tier: Mapped[str] = mapped_column(
        String(20),
        default=OrganizationTier.STARTER.value,
        nullable=False,
        comment="Subscription tier: starter|pro|enterprise",
    )

    # OBBB-specific configuration
    tip_credit_enabled: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether tip credit calculations are enabled",
    )
    overtime_credit_enabled: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether overtime credit calculations are enabled",
    )
    penalty_guarantee_active: Mapped[bool] = mapped_column(
        default=False,
        comment="Enterprise-only: Penalty Guarantee enrollment status",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=OrganizationStatus.ACTIVE.value,
        nullable=False,
        comment="Account status: active|suspended|closed",
    )

    # FLSA Configuration
    workweek_start: Mapped[str] = mapped_column(
        String(10),
        default="sunday",
        nullable=False,
        comment="FLSA workweek start day (sunday-saturday)",
    )

    # Flexible settings stored as JSONB
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Organization-specific configuration (state OT rules, tip pool methods, etc.)",
    )

    # Contact information
    primary_contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    primary_contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Timestamps for business events
    onboarded_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Timestamp when onboarding was completed",
    )

    # Relationships
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    integrations: Mapped[list["Integration"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    calculation_runs: Mapped[list["CalculationRun"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "ein ~ '^[0-9]{2}-[0-9]{7}$'",
            name="valid_ein_format",
        ),
        CheckConstraint(
            "tier IN ('starter', 'pro', 'enterprise')",
            name="valid_tier",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended', 'closed')",
            name="valid_status",
        ),
        CheckConstraint(
            "workweek_start IN ('sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="valid_workweek_start",
        ),
        Index("ix_organizations_ein", "ein"),
        Index("ix_organizations_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} (EIN: {self.ein})>"
