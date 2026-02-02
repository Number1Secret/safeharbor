"""
Premium Engine Schemas

Input/output models for FLSA Section 7 Regular Rate calculation.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class RegularRateInput(BaseModel):
    """
    Input for FLSA Section 7 Regular Rate calculation.

    Per 29 CFR § 778.109, the regular rate includes all remuneration
    for employment except specific exclusions under FLSA Section 207(e).
    """

    employee_id: str = Field(..., description="Unique employee identifier")
    period_start: str = Field(..., description="Period start date (YYYY-MM-DD)")
    period_end: str = Field(..., description="Period end date (YYYY-MM-DD)")

    # Hours worked
    regular_hours: Decimal = Field(..., ge=0, description="Regular hours worked")
    overtime_hours: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Federal overtime hours (>40/week)",
    )
    state_overtime_hours: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="State-specific OT hours (e.g., CA daily OT)",
    )
    double_time_hours: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Double-time hours (excluded from OBBB qualified amount)",
    )

    # Wage components (included in regular rate)
    hourly_rate: Decimal = Field(..., ge=0, description="Primary hourly rate")
    shift_differentials: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Shift differential pay",
    )
    non_discretionary_bonuses: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Non-discretionary bonuses (production, attendance, etc.)",
    )
    commissions: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Commission earnings",
    )
    piece_rate_earnings: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Piece-rate earnings",
    )

    # Exclusions from regular rate (FLSA 207(e))
    discretionary_bonuses: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Discretionary bonuses (holiday, year-end gifts)",
    )
    gifts: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Gifts not tied to hours/production",
    )
    expense_reimbursements: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Travel, uniform, tool reimbursements",
    )
    premium_pay_already_counted: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Premium pay already credited toward OT (weekend/holiday premiums)",
    )


class RegularRateOutput(BaseModel):
    """
    Output from FLSA Regular Rate calculation.

    Includes the calculated regular rate, overtime premium,
    and full breakdown for audit trail.
    """

    employee_id: str
    period_start: str
    period_end: str

    # Calculated values
    total_hours: Decimal = Field(..., description="Total hours worked")
    total_compensation: Decimal = Field(..., description="Total includable compensation")
    regular_rate: Decimal = Field(..., description="FLSA Regular Rate per hour (4 decimal places)")

    # Overtime calculations
    overtime_hours_qualified: Decimal = Field(
        ...,
        description="OT hours qualifying for OBBB (excludes double-time)",
    )
    overtime_premium: Decimal = Field(
        ...,
        description="Total OT premium (0.5x × Regular Rate × OT Hours)",
    )
    qualified_ot_premium: Decimal = Field(
        ...,
        description="OBBB qualified overtime premium (excludes double-time hours)",
    )

    # Calculation breakdown for audit
    regular_rate_components: dict = Field(
        ...,
        description="Itemized components included in regular rate",
    )
    excluded_components: dict = Field(
        ...,
        description="Itemized components excluded per FLSA 207(e)",
    )

    # Validation flags
    minimum_wage_applied: bool = Field(
        default=False,
        description="True if federal minimum wage was used as floor",
    )
    calculation_notes: list[str] = Field(
        default_factory=list,
        description="Any notes about the calculation",
    )


class TipCreditInput(BaseModel):
    """Input for tip credit calculation."""

    employee_id: str
    period_start: str
    period_end: str

    # Tip amounts
    cash_tips: Decimal = Field(default=Decimal("0"), ge=0)
    charged_tips: Decimal = Field(default=Decimal("0"), ge=0)
    tip_pool_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    tip_pool_distribution: Decimal = Field(default=Decimal("0"), ge=0)

    # TTOC classification
    ttoc_code: str | None = Field(default=None, description="Treasury Tipped Occupation Code")
    is_tipped_occupation: bool = Field(default=False)

    # Hours in tipped vs non-tipped roles (for dual-job employees)
    hours_in_tipped_role: Decimal = Field(default=Decimal("0"), ge=0)
    hours_in_non_tipped_role: Decimal = Field(default=Decimal("0"), ge=0)


class TipCreditOutput(BaseModel):
    """Output from tip credit calculation."""

    employee_id: str
    period_start: str
    period_end: str

    # Tip totals
    total_tips: Decimal
    qualified_tips: Decimal

    # Breakdown
    cash_tips: Decimal
    charged_tips: Decimal
    net_pool_adjustment: Decimal

    # Apportionment (for dual-job)
    tipped_role_percentage: Decimal
    apportionment_applied: bool

    # OBBB qualification
    is_eligible: bool
    ineligibility_reason: str | None = None
