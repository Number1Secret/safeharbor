"""
EmployeeCalculation Model

Per-employee calculation result within a CalculationRun.
Stores all calculated values and full audit trail.
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.calculation_run import CalculationRun
    from backend.models.employee import Employee


class CalculationStatus(str, Enum):
    """Status of individual employee calculation."""

    PENDING = "pending"  # Not yet processed
    COMPLETED = "completed"  # Successfully calculated
    ERROR = "error"  # Calculation failed
    FLAGGED = "flagged"  # Requires human review


class AnomalyFlag(str, Enum):
    """Types of anomalies that can be flagged."""

    HIGH_OT_VARIANCE = "high_ot_variance"  # OT changed significantly from last period
    MISSING_TIP_DATA = "missing_tip_data"  # Tipped employee with no tip records
    TTOC_LOW_CONFIDENCE = "ttoc_low_confidence"  # AI classification below threshold
    PHASE_OUT_RISK = "phase_out_risk"  # Approaching MAGI phase-out
    DUAL_JOB_DETECTED = "dual_job_detected"  # Employee works multiple job codes
    REGULAR_RATE_ANOMALY = "regular_rate_anomaly"  # Unusual regular rate calculation
    NEGATIVE_VALUE = "negative_value"  # Calculated negative (correction needed)


class EmployeeCalculation(TimestampMixin, Base):
    """
    Per-employee calculation result.

    Stores the output from all three calculation engines:
    - Premium Engine: Regular Rate and OT Premium
    - Occupation AI: TTOC classification
    - Phase-Out Filter: MAGI-based reductions

    This record is effectively immutable once created; corrections
    result in new calculation runs rather than modifications.
    """

    __tablename__ = "employee_calculations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    calculation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )

    # === Premium Engine Outputs (FLSA Section 7) ===

    # Hours worked
    total_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Total hours worked in period",
    )
    regular_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Regular (non-overtime) hours",
    )
    overtime_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Federal overtime hours (>40/week)",
    )
    state_overtime_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="State-specific overtime hours (e.g., CA daily OT)",
    )
    double_time_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Double-time hours (excluded from OBBB)",
    )

    # Compensation
    gross_wages: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Total gross wages for period",
    )
    hourly_rate_primary: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="Primary hourly rate",
    )

    # FLSA Regular Rate calculation
    regular_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Calculated FLSA Section 7 Regular Rate of Pay",
    )
    regular_rate_components: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Itemized components included in regular rate calculation",
    )

    # Overtime premium
    overtime_premium_calculated: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Calculated OT premium (0.5x × Regular Rate × OT Hours)",
    )
    qualified_ot_premium: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Qualified OT premium for OBBB (excludes double-time)",
    )

    # === Tip Credit Calculation ===

    cash_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Cash tips received",
    )
    charged_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Credit card tips received",
    )
    tip_pool_out: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Tips contributed to pool",
    )
    tip_pool_in: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Tips received from pool",
    )
    total_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Total tips (cash + charged + pool adjustments)",
    )
    qualified_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Qualified tips for OBBB exemption",
    )

    # === TTOC from Occupation AI ===

    ttoc_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Treasury Tipped Occupation Code at time of calculation",
    )
    ttoc_confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="AI confidence score (0.0-1.0)",
    )
    ttoc_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI reasoning for classification",
    )
    is_tipped_occupation: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether employee qualifies for tip exemption",
    )

    # === Phase-Out Filter Results ===

    magi_estimated: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Estimated MAGI for phase-out calculation",
    )
    filing_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Filing status used for phase-out",
    )
    phase_out_threshold_start: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Phase-out threshold start for filing status",
    )
    phase_out_threshold_end: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Phase-out threshold end for filing status",
    )
    phase_out_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Phase-out percentage (0-100)",
    )
    phase_out_reduction_ot: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Reduction to OT credit due to phase-out",
    )
    phase_out_reduction_tips: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Reduction to tip credit due to phase-out",
    )

    # === Final Credit Amounts (after phase-out) ===

    ot_credit_final: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Final OT credit after phase-out",
    )
    tip_credit_final: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Final tip credit after phase-out",
    )
    combined_credit_final: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Total combined credit (OT + tips after phase-out)",
    )

    # === Calculation Status ===

    status: Mapped[str] = mapped_column(
        String(20),
        default=CalculationStatus.PENDING.value,
        nullable=False,
        comment="Calculation status: pending|completed|error|flagged",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if status is 'error'",
    )
    anomaly_flags: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of anomaly codes requiring review",
    )
    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from human review",
    )

    # === Audit Trail ===

    calculation_trace: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Complete calculation inputs/outputs for reproducibility",
    )
    input_data_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of source data for integrity verification",
    )
    engine_versions: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Version of each engine used for this calculation",
    )

    # Relationships
    calculation_run: Mapped["CalculationRun"] = relationship(
        back_populates="employee_calculations",
    )
    employee: Mapped["Employee"] = relationship(
        back_populates="calculations",
    )

    __table_args__ = (
        UniqueConstraint(
            "calculation_run_id",
            "employee_id",
            name="uq_run_employee",
        ),
        Index("ix_employee_calculations_run_id", "calculation_run_id"),
        Index("ix_employee_calculations_employee_id", "employee_id"),
        Index("ix_employee_calculations_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<EmployeeCalculation {self.employee_id} run={self.calculation_run_id} ({self.status})>"

    @property
    def has_anomalies(self) -> bool:
        """Check if calculation has any anomaly flags."""
        return len(self.anomaly_flags) > 0

    @property
    def needs_review(self) -> bool:
        """Check if calculation needs human review."""
        return self.status == CalculationStatus.FLAGGED.value or self.has_anomalies
