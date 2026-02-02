"""
Phase-Out Filter Schemas

Input/output models for MAGI-based phase-out calculation.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PhaseOutInput(BaseModel):
    """
    Input for MAGI-based phase-out calculation.

    Per the OBBB, tip and overtime credits phase out for higher-income
    taxpayers based on Modified Adjusted Gross Income (MAGI).
    """

    employee_id: str = Field(..., description="Unique employee identifier")
    tax_year: int = Field(..., description="Tax year for calculation")

    # MAGI components
    wages: Decimal = Field(..., ge=0, description="W-2 wages")
    self_employment_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Self-employment income",
    )
    investment_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Investment income (interest, dividends, capital gains)",
    )
    other_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Other income sources",
    )
    above_the_line_deductions: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Above-the-line deductions (IRA, student loan interest, etc.)",
    )

    # Filing status
    filing_status: Literal[
        "single", "married_joint", "married_separate", "head_of_household"
    ] = Field(
        ...,
        description="Tax filing status for determining phase-out thresholds",
    )

    # Credit amounts before phase-out
    ot_credit_pre_phase_out: Decimal = Field(
        ...,
        ge=0,
        description="Overtime credit amount before phase-out",
    )
    tip_credit_pre_phase_out: Decimal = Field(
        ...,
        ge=0,
        description="Tip credit amount before phase-out",
    )


class PhaseOutOutput(BaseModel):
    """
    Output from MAGI phase-out calculation.

    Shows the calculated MAGI, applicable thresholds, phase-out
    percentage, and final credit amounts after reduction.
    """

    employee_id: str
    tax_year: int

    # MAGI calculation
    calculated_magi: Decimal = Field(..., description="Calculated MAGI")

    # Threshold determination
    filing_status: str
    phase_out_threshold_start: Decimal = Field(
        ...,
        description="MAGI at which phase-out begins",
    )
    phase_out_threshold_end: Decimal = Field(
        ...,
        description="MAGI at which credits are fully phased out",
    )

    # Phase-out calculation
    excess_over_threshold: Decimal = Field(
        ...,
        description="Amount by which MAGI exceeds threshold start",
    )
    phase_out_range: Decimal = Field(
        ...,
        description="Range between threshold start and end",
    )
    phase_out_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of credit phased out (0-100)",
    )

    # Credit amounts
    ot_credit_pre: Decimal = Field(..., description="OT credit before phase-out")
    tip_credit_pre: Decimal = Field(..., description="Tip credit before phase-out")
    ot_credit_reduction: Decimal = Field(..., description="OT credit reduction amount")
    tip_credit_reduction: Decimal = Field(..., description="Tip credit reduction amount")
    ot_credit_final: Decimal = Field(..., description="OT credit after phase-out")
    tip_credit_final: Decimal = Field(..., description="Tip credit after phase-out")
    combined_credit_final: Decimal = Field(..., description="Total credit after phase-out")

    # Status flags
    is_fully_phased_out: bool = Field(
        ...,
        description="True if credits are completely phased out",
    )
    is_partially_phased_out: bool = Field(
        ...,
        description="True if credits are partially reduced",
    )
    is_no_phase_out: bool = Field(
        ...,
        description="True if MAGI is below phase-out threshold",
    )

    # Notes
    calculation_notes: list[str] = Field(
        default_factory=list,
        description="Notes about the calculation",
    )
