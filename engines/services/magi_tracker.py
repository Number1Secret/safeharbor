"""
MAGI Tracker Service

Calculates Modified Adjusted Gross Income and applies
OBBB phase-out rules to tax credits.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from engines.schemas.phase_out import PhaseOutInput, PhaseOutOutput

# OBBB Phase-out thresholds per PRD Section 2.3.3
# These are hypothetical thresholds based on the PRD specification
PHASE_OUT_THRESHOLDS: dict[int, dict[str, dict[str, Decimal]]] = {
    2025: {
        "single": {
            "start": Decimal("75000"),
            "end": Decimal("100000"),
        },
        "married_joint": {
            "start": Decimal("150000"),
            "end": Decimal("200000"),
        },
        "married_separate": {
            "start": Decimal("75000"),
            "end": Decimal("100000"),
        },
        "head_of_household": {
            "start": Decimal("112500"),
            "end": Decimal("150000"),
        },
    },
    2026: {
        # Thresholds may be adjusted for inflation
        "single": {
            "start": Decimal("77000"),
            "end": Decimal("102000"),
        },
        "married_joint": {
            "start": Decimal("154000"),
            "end": Decimal("204000"),
        },
        "married_separate": {
            "start": Decimal("77000"),
            "end": Decimal("102000"),
        },
        "head_of_household": {
            "start": Decimal("115500"),
            "end": Decimal("153500"),
        },
    },
}


def get_thresholds(
    tax_year: int, filing_status: str
) -> tuple[Decimal, Decimal]:
    """
    Get phase-out thresholds for a given tax year and filing status.

    Falls back to most recent available thresholds if year not found.
    """
    # Use the tax year's thresholds, or fall back to 2025
    year_thresholds = PHASE_OUT_THRESHOLDS.get(
        tax_year, PHASE_OUT_THRESHOLDS[2025]
    )

    # Get filing status thresholds, default to single
    status_thresholds = year_thresholds.get(
        filing_status, year_thresholds["single"]
    )

    return status_thresholds["start"], status_thresholds["end"]


def calculate_magi(input_data: PhaseOutInput) -> Decimal:
    """
    Calculate Modified Adjusted Gross Income.

    MAGI = Wages + Self-Employment + Investment + Other - Above-the-Line Deductions
    """
    magi = (
        input_data.wages
        + input_data.self_employment_income
        + input_data.investment_income
        + input_data.other_income
        - input_data.above_the_line_deductions
    )
    return magi


def calculate_phase_out(input_data: PhaseOutInput) -> PhaseOutOutput:
    """
    Calculate MAGI-based phase-out for OBBB tax credits.

    The phase-out is linear between the start and end thresholds:
    - MAGI <= Start: No phase-out (0%)
    - MAGI >= End: Full phase-out (100%)
    - Start < MAGI < End: Linear interpolation

    Phase-out rates per PRD Section 2.3.3:
    - Single: 4% per $1,000 over threshold
    - Married Joint: 2% per $1,000 over threshold
    - Head of Household: 2.67% per $1,000 over threshold
    """
    notes: list[str] = []

    # Calculate MAGI
    magi = calculate_magi(input_data)

    # Get thresholds
    threshold_start, threshold_end = get_thresholds(
        input_data.tax_year, input_data.filing_status
    )
    phase_out_range = threshold_end - threshold_start

    # Calculate phase-out percentage
    if magi <= threshold_start:
        # No phase-out
        excess = Decimal("0")
        phase_out_pct = Decimal("0")
        is_fully_phased_out = False
        is_partially_phased_out = False
        is_no_phase_out = True
    elif magi >= threshold_end:
        # Full phase-out
        excess = magi - threshold_start
        phase_out_pct = Decimal("100")
        is_fully_phased_out = True
        is_partially_phased_out = False
        is_no_phase_out = False
        notes.append(f"MAGI ${magi:,.2f} exceeds phase-out threshold ${threshold_end:,.2f}")
    else:
        # Partial phase-out (linear)
        excess = magi - threshold_start
        phase_out_pct = ((excess / phase_out_range) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        is_fully_phased_out = False
        is_partially_phased_out = True
        is_no_phase_out = False
        notes.append(
            f"MAGI ${magi:,.2f} is ${excess:,.2f} over threshold; "
            f"{phase_out_pct}% phase-out applied"
        )

    # Apply phase-out to credits
    reduction_factor = phase_out_pct / 100

    ot_reduction = (input_data.ot_credit_pre_phase_out * reduction_factor).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    tip_reduction = (input_data.tip_credit_pre_phase_out * reduction_factor).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    ot_final = input_data.ot_credit_pre_phase_out - ot_reduction
    tip_final = input_data.tip_credit_pre_phase_out - tip_reduction
    combined_final = ot_final + tip_final

    return PhaseOutOutput(
        employee_id=input_data.employee_id,
        tax_year=input_data.tax_year,
        calculated_magi=magi,
        filing_status=input_data.filing_status,
        phase_out_threshold_start=threshold_start,
        phase_out_threshold_end=threshold_end,
        excess_over_threshold=excess,
        phase_out_range=phase_out_range,
        phase_out_percentage=phase_out_pct,
        ot_credit_pre=input_data.ot_credit_pre_phase_out,
        tip_credit_pre=input_data.tip_credit_pre_phase_out,
        ot_credit_reduction=ot_reduction,
        tip_credit_reduction=tip_reduction,
        ot_credit_final=ot_final,
        tip_credit_final=tip_final,
        combined_credit_final=combined_final,
        is_fully_phased_out=is_fully_phased_out,
        is_partially_phased_out=is_partially_phased_out,
        is_no_phase_out=is_no_phase_out,
        calculation_notes=notes,
    )


def estimate_annual_magi(
    ytd_wages: Decimal,
    pay_periods_elapsed: int,
    total_pay_periods: int,
    other_income: Decimal = Decimal("0"),
) -> Decimal:
    """
    Estimate annual MAGI based on year-to-date data.

    Uses linear projection: (YTD / elapsed periods) * total periods

    Args:
        ytd_wages: Year-to-date wages
        pay_periods_elapsed: Number of pay periods completed
        total_pay_periods: Total pay periods in the year (26 for biweekly, 24 for semi-monthly)
        other_income: Estimated other income for the year

    Returns:
        Estimated annual MAGI
    """
    if pay_periods_elapsed == 0:
        return other_income

    projected_wages = (ytd_wages / pay_periods_elapsed) * total_pay_periods
    return projected_wages + other_income


def check_phase_out_risk(
    current_magi: Decimal,
    filing_status: str,
    tax_year: int = 2025,
) -> tuple[bool, Decimal, str]:
    """
    Check if an employee is at risk of phase-out.

    Returns:
        Tuple of (is_at_risk, percentage_to_threshold, risk_level)
        risk_level: "none" | "approaching" | "in_phase_out" | "fully_phased_out"
    """
    threshold_start, threshold_end = get_thresholds(tax_year, filing_status)

    if current_magi >= threshold_end:
        return True, Decimal("100"), "fully_phased_out"
    elif current_magi >= threshold_start:
        pct_through = ((current_magi - threshold_start) / (threshold_end - threshold_start)) * 100
        return True, pct_through, "in_phase_out"
    elif current_magi >= threshold_start * Decimal("0.9"):
        # Within 10% of threshold
        pct_to_threshold = (current_magi / threshold_start) * 100
        return True, pct_to_threshold, "approaching"
    else:
        pct_to_threshold = (current_magi / threshold_start) * 100
        return False, pct_to_threshold, "none"
