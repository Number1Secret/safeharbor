"""
CalculationRun Model

Batch calculation run for a pay period or tax period.
Tracks the processing lifecycle with state machine transitions.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import AuditMixin, Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.employee_calculation import EmployeeCalculation
    from backend.models.organization import Organization


class RunType(str, Enum):
    """Type of calculation run."""

    PAY_PERIOD = "pay_period"  # Regular payroll period
    QUARTERLY = "quarterly"  # Quarterly reconciliation
    ANNUAL = "annual"  # Year-end W-2 preparation
    AD_HOC = "ad_hoc"  # On-demand calculation
    RETRO_AUDIT = "retro_audit"  # Historical audit (Retro-Cleanse)


class RunStatus(str, Enum):
    """
    Calculation run status (state machine).

    State transitions:
    pending -> syncing -> calculating -> pending_approval -> approved -> finalized
                                      -> rejected (can restart)
    Any state can transition to -> error
    """

    PENDING = "pending"  # Created, not yet started
    SYNCING = "syncing"  # Pulling data from integrations
    CALCULATING = "calculating"  # Running calculation engines
    PENDING_APPROVAL = "pending_approval"  # Awaiting human review
    APPROVED = "approved"  # Approved, ready for finalization
    REJECTED = "rejected"  # Rejected, needs corrections
    FINALIZED = "finalized"  # Locked, written to vault
    ERROR = "error"  # Failed, check error details


class CalculationRun(TimestampMixin, AuditMixin, Base):
    """
    Batch calculation run for a pay period.

    Orchestrates the calculation pipeline: sync data from integrations,
    run calculation engines (Premium, Occupation AI, Phase-Out), and
    aggregate results for approval before finalizing to the vault.
    """

    __tablename__ = "calculation_runs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Run identification
    run_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Run type: pay_period|quarterly|annual|ad_hoc|retro_audit",
    )
    period_start: Mapped[date] = mapped_column(
        nullable=False,
        comment="Start date of calculation period",
    )
    period_end: Mapped[date] = mapped_column(
        nullable=False,
        comment="End date of calculation period",
    )
    tax_year: Mapped[int] = mapped_column(
        nullable=False,
        comment="Tax year for this calculation",
    )

    # State machine
    status: Mapped[str] = mapped_column(
        String(30),
        default=RunStatus.PENDING.value,
        nullable=False,
        comment="Run status: pending|syncing|calculating|pending_approval|approved|rejected|finalized|error",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if status is 'error'",
    )

    # Progress tracking
    total_employees: Mapped[int] = mapped_column(
        default=0,
        comment="Total employees in scope for this run",
    )
    processed_employees: Mapped[int] = mapped_column(
        default=0,
        comment="Employees successfully processed",
    )
    failed_employees: Mapped[int] = mapped_column(
        default=0,
        comment="Employees with calculation errors",
    )
    flagged_employees: Mapped[int] = mapped_column(
        default=0,
        comment="Employees flagged for human review",
    )

    # Aggregated results (summary)
    total_qualified_ot_premium: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Sum of qualified OT premiums across all employees",
    )
    total_qualified_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Sum of qualified tips across all employees",
    )
    total_combined_credit: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Total combined tax credit (OT + tips)",
    )
    total_phase_out_reduction: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Total reduction due to MAGI phase-outs",
    )

    # Comparison with previous period (for anomaly detection)
    previous_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("calculation_runs.id"),
        nullable=True,
        comment="Reference to previous run for comparison",
    )
    delta_qualified_ot: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Change in OT credit vs. previous period",
    )
    delta_qualified_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Change in tip credit vs. previous period",
    )

    # Approval workflow
    submitted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When run was submitted for approval",
    )
    submitted_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User who submitted for approval",
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When run was approved",
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User who approved the run",
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection if status is 'rejected'",
    )

    # Finalization
    finalized_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When run was finalized and locked",
    )
    finalized_vault_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("compliance_vault.id"),
        nullable=True,
        comment="Immutable vault entry created on finalization",
    )

    # Engine versions used (for reproducibility)
    engine_versions: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Version of each engine used: {'premium_engine': 'v1.0.0', 'occupation_ai': 'v1.0.0'}",
    )

    # Processing metadata
    sync_started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    sync_completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    calculation_started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    calculation_completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        back_populates="calculation_runs",
    )
    employee_calculations: Mapped[list["EmployeeCalculation"]] = relationship(
        back_populates="calculation_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    previous_run: Mapped["CalculationRun | None"] = relationship(
        remote_side=[id],
        foreign_keys=[previous_run_id],
    )

    __table_args__ = (
        CheckConstraint(
            "period_end >= period_start",
            name="valid_period_range",
        ),
        CheckConstraint(
            "run_type IN ('pay_period', 'quarterly', 'annual', 'ad_hoc', 'retro_audit')",
            name="valid_run_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'syncing', 'calculating', 'pending_approval', 'approved', 'rejected', 'finalized', 'error')",
            name="valid_run_status",
        ),
        Index("ix_calculation_runs_org_id", "organization_id"),
        Index("ix_calculation_runs_status", "status"),
        Index("ix_calculation_runs_org_period", "organization_id", "period_start", "period_end"),
        Index("ix_calculation_runs_tax_year", "organization_id", "tax_year"),
    )

    def __repr__(self) -> str:
        return f"<CalculationRun {self.id} ({self.run_type}: {self.period_start} - {self.period_end}, {self.status})>"

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_employees == 0:
            return 0.0
        return (self.processed_employees / self.total_employees) * 100

    @property
    def is_complete(self) -> bool:
        """Check if run is in a terminal state."""
        return self.status in (RunStatus.FINALIZED.value, RunStatus.ERROR.value)

    @property
    def can_approve(self) -> bool:
        """Check if run can be approved."""
        return self.status == RunStatus.PENDING_APPROVAL.value

    @property
    def can_finalize(self) -> bool:
        """Check if run can be finalized."""
        return self.status == RunStatus.APPROVED.value
