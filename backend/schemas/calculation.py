"""
Calculation Pydantic Schemas

API request/response models for Calculation endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalculationRunCreate(BaseModel):
    """Schema for creating a new calculation run."""

    run_type: Literal["pay_period", "quarterly", "annual", "ad_hoc", "retro_audit"] = Field(
        default="pay_period",
        description="Type of calculation run",
    )
    period_start: date = Field(..., description="Start date of calculation period")
    period_end: date = Field(..., description="End date of calculation period")
    tax_year: int = Field(default=2025, ge=2024, le=2030)


class CalculationRunResponse(BaseModel):
    """Schema for calculation run response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    run_type: str
    period_start: date
    period_end: date
    tax_year: int
    status: str
    error_message: str | None

    # Progress
    total_employees: int
    processed_employees: int
    failed_employees: int
    flagged_employees: int

    # Totals (after calculation)
    total_qualified_ot_premium: Decimal | None
    total_qualified_tips: Decimal | None
    total_combined_credit: Decimal | None
    total_phase_out_reduction: Decimal | None

    # Comparison with previous
    previous_run_id: UUID | None
    delta_qualified_ot: Decimal | None
    delta_qualified_tips: Decimal | None

    # Workflow timestamps
    submitted_at: datetime | None
    submitted_by: UUID | None
    approved_at: datetime | None
    approved_by: UUID | None
    finalized_at: datetime | None
    rejection_reason: str | None

    # Engine versions
    engine_versions: dict

    # Timestamps
    created_at: datetime
    updated_at: datetime


class CalculationRunSummary(BaseModel):
    """Summary schema for calculation run listing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_type: str
    period_start: date
    period_end: date
    status: str
    total_employees: int
    processed_employees: int
    total_combined_credit: Decimal | None
    created_at: datetime

    # Progress percentage
    progress_percentage: float = 0.0


class CalculationRunListResponse(BaseModel):
    """Schema for paginated calculation run list."""

    items: list[CalculationRunSummary]
    total: int
    page: int
    page_size: int
    pages: int


class EmployeeCalculationResponse(BaseModel):
    """Schema for individual employee calculation result."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calculation_run_id: UUID
    employee_id: UUID

    # Hours
    total_hours: Decimal | None
    regular_hours: Decimal | None
    overtime_hours: Decimal | None
    state_overtime_hours: Decimal | None
    double_time_hours: Decimal | None

    # Wages
    gross_wages: Decimal | None
    hourly_rate_primary: Decimal | None

    # FLSA Regular Rate
    regular_rate: Decimal | None
    regular_rate_components: dict

    # Overtime
    overtime_premium_calculated: Decimal | None
    qualified_ot_premium: Decimal | None

    # Tips
    cash_tips: Decimal | None
    charged_tips: Decimal | None
    total_tips: Decimal | None
    qualified_tips: Decimal | None

    # TTOC
    ttoc_code: str | None
    ttoc_confidence: float | None
    is_tipped_occupation: bool

    # Phase-out
    magi_estimated: Decimal | None
    filing_status: str | None
    phase_out_percentage: Decimal | None
    phase_out_reduction_ot: Decimal | None
    phase_out_reduction_tips: Decimal | None

    # Final amounts
    ot_credit_final: Decimal | None
    tip_credit_final: Decimal | None
    combined_credit_final: Decimal | None

    # Status
    status: str
    error_message: str | None
    anomaly_flags: list[str]

    created_at: datetime


class CalculationApprovalRequest(BaseModel):
    """Schema for approving or rejecting a calculation run."""

    action: Literal["approve", "reject"]
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Required for rejection, optional for approval",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Additional notes for the approval",
    )


class CalculationExportRequest(BaseModel):
    """Schema for exporting calculation data."""

    format: Literal["csv", "json", "w2_import"] = Field(
        default="csv",
        description="Export format",
    )
    include_details: bool = Field(
        default=False,
        description="Include detailed calculation breakdown",
    )


class RegularRateBreakdown(BaseModel):
    """Detailed breakdown of regular rate calculation."""

    base_wages: Decimal
    shift_differentials: Decimal
    non_discretionary_bonuses: Decimal
    commissions: Decimal
    piece_rate: Decimal
    total_includable: Decimal
    total_hours: Decimal
    regular_rate: Decimal

    # Excluded items
    discretionary_bonuses: Decimal
    gifts: Decimal
    expense_reimbursements: Decimal
    premium_pay_excluded: Decimal


class PhaseOutBreakdown(BaseModel):
    """Detailed breakdown of phase-out calculation."""

    magi_estimated: Decimal
    filing_status: str
    threshold_start: Decimal
    threshold_end: Decimal
    excess_over_threshold: Decimal
    phase_out_range: Decimal
    phase_out_percentage: Decimal

    # Credits before phase-out
    ot_credit_pre: Decimal
    tip_credit_pre: Decimal

    # Reductions
    ot_reduction: Decimal
    tip_reduction: Decimal

    # Credits after phase-out
    ot_credit_final: Decimal
    tip_credit_final: Decimal
