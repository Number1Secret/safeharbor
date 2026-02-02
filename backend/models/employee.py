"""
Employee Model

Employee records for tax calculation purposes.
Links payroll data, tip information, and occupation classification.
"""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import AuditMixin, Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.employee_calculation import EmployeeCalculation
    from backend.models.organization import Organization
    from backend.models.ttoc_classification import TTOCClassification


class EmploymentStatus(str, Enum):
    """Employee employment status."""

    ACTIVE = "active"
    TERMINATED = "terminated"
    LEAVE = "leave"


class FilingStatus(str, Enum):
    """Tax filing status for MAGI phase-out calculations."""

    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class Employee(TimestampMixin, AuditMixin, Base):
    """
    Employee record for tax calculation purposes.

    Stores employee identity, external system IDs for integration mapping,
    and TTOC classification for tip credit eligibility. SSN is stored as
    a hash for matching purposes without retaining sensitive data.
    """

    __tablename__ = "employees"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # External identifiers for integration mapping
    external_ids: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="External system IDs: {'adp': 'xxx', 'gusto': 'yyy', 'toast': 'zzz'}",
    )

    # Core identity
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    ssn_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of SSN for matching without storing raw value",
    )

    # Employment details
    hire_date: Mapped[date] = mapped_column(
        nullable=False,
    )
    termination_date: Mapped[date | None] = mapped_column(
        nullable=True,
    )
    employment_status: Mapped[str] = mapped_column(
        String(20),
        default=EmploymentStatus.ACTIVE.value,
        nullable=False,
        comment="Employment status: active|terminated|leave",
    )

    # Job information
    job_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Current job title for TTOC classification",
    )
    job_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Job description text for AI classification",
    )
    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    duties: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of job duties for TTOC classification",
    )

    # Pay information
    hourly_rate: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Primary hourly rate (may have multiple rates per shift)",
    )
    is_hourly: Mapped[bool] = mapped_column(
        default=True,
        comment="True for hourly employees, False for salaried",
    )

    # TTOC Classification (from Occupation AI)
    ttoc_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Treasury Tipped Occupation Code (e.g., '12401' for Server)",
    )
    ttoc_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ttoc_classifications.id"),
        nullable=True,
        comment="Reference to current TTOC classification record",
    )
    ttoc_title: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="TTOC title category (e.g., 'server', 'bartender')",
    )
    ttoc_verified: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether TTOC has been human-verified",
    )
    ttoc_verified_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    ttoc_verified_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    # MAGI tracking for phase-out (per PRD Section 2.3.3)
    filing_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Tax filing status for phase-out: single|married_joint|married_separate|head_of_household",
    )
    estimated_annual_magi: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Estimated Modified Adjusted Gross Income for phase-out calculations",
    )

    # Year-to-date tracking
    ytd_gross_wages: Mapped[float] = mapped_column(
        default=0.0,
        comment="Year-to-date gross wages",
    )
    ytd_overtime_hours: Mapped[float] = mapped_column(
        default=0.0,
        comment="Year-to-date overtime hours",
    )
    ytd_tips: Mapped[float] = mapped_column(
        default=0.0,
        comment="Year-to-date tips received",
    )
    ytd_qualified_ot_premium: Mapped[float] = mapped_column(
        default=0.0,
        comment="Year-to-date qualified overtime premium (OBBB)",
    )
    ytd_qualified_tips: Mapped[float] = mapped_column(
        default=0.0,
        comment="Year-to-date qualified tips (OBBB)",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        back_populates="employees",
    )
    calculations: Mapped[list["EmployeeCalculation"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ttoc_classification: Mapped["TTOCClassification | None"] = relationship(
        foreign_keys=[ttoc_classification_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ssn_hash",
            name="uq_employee_org_ssn",
        ),
        Index("ix_employees_organization_id", "organization_id"),
        Index("ix_employees_employment_status", "employment_status"),
        Index("ix_employees_ttoc_code", "ttoc_code"),
        Index("ix_employees_org_status", "organization_id", "employment_status"),
    )

    def __repr__(self) -> str:
        return f"<Employee {self.first_name} {self.last_name} ({self.employment_status})>"

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_tipped_occupation(self) -> bool:
        """Check if employee is in a qualifying tipped occupation."""
        return self.ttoc_code is not None
