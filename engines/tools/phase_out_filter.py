"""
Phase-Out Filter MCP Tool

MAGI-based phase-out calculation exposed as an MCP tool.
"""

from decimal import Decimal
from typing import Literal

from fastmcp import FastMCP

from engines.schemas.phase_out import PhaseOutInput, PhaseOutOutput
from engines.services.magi_tracker import (
    calculate_phase_out,
    check_phase_out_risk,
    estimate_annual_magi,
)

# Use the same MCP instance as premium_engine
from engines.tools.premium_engine import mcp


@mcp.tool()
async def calculate_magi_phase_out(
    employee_id: str,
    tax_year: int,
    wages: float,
    filing_status: Literal["single", "married_joint", "married_separate", "head_of_household"],
    ot_credit_pre_phase_out: float,
    tip_credit_pre_phase_out: float,
    self_employment_income: float = 0.0,
    investment_income: float = 0.0,
    other_income: float = 0.0,
    above_the_line_deductions: float = 0.0,
) -> dict:
    """
    Calculate MAGI-based phase-out for OBBB tax credits.

    The One Big Beautiful Bill provides tip and overtime credits that
    phase out for higher-income taxpayers based on Modified Adjusted
    Gross Income (MAGI).

    Phase-out thresholds (2025):
    - Single: $75,000 - $100,000 (4% per $1,000 over)
    - Married Filing Jointly: $150,000 - $200,000 (2% per $1,000 over)
    - Head of Household: $112,500 - $150,000 (2.67% per $1,000 over)

    Args:
        employee_id: Unique employee identifier
        tax_year: Tax year for threshold lookup
        wages: W-2 wages
        filing_status: Tax filing status
        ot_credit_pre_phase_out: Overtime credit before phase-out
        tip_credit_pre_phase_out: Tip credit before phase-out
        self_employment_income: Self-employment income
        investment_income: Interest, dividends, capital gains
        other_income: Other income sources
        above_the_line_deductions: IRA, student loan interest, etc.

    Returns:
        Dictionary with MAGI, phase-out percentage, and final credits

    Example:
        Single filer with $85,000 MAGI:
        - Excess over $75,000: $10,000
        - Phase-out: $10,000 / $25,000 range = 40%
        - $100 OT credit → $60 after phase-out
    """
    input_data = PhaseOutInput(
        employee_id=employee_id,
        tax_year=tax_year,
        wages=Decimal(str(wages)),
        self_employment_income=Decimal(str(self_employment_income)),
        investment_income=Decimal(str(investment_income)),
        other_income=Decimal(str(other_income)),
        above_the_line_deductions=Decimal(str(above_the_line_deductions)),
        filing_status=filing_status,
        ot_credit_pre_phase_out=Decimal(str(ot_credit_pre_phase_out)),
        tip_credit_pre_phase_out=Decimal(str(tip_credit_pre_phase_out)),
    )

    result = calculate_phase_out(input_data)

    return {
        "employee_id": result.employee_id,
        "tax_year": result.tax_year,
        "calculated_magi": float(result.calculated_magi),
        "filing_status": result.filing_status,
        "phase_out_threshold_start": float(result.phase_out_threshold_start),
        "phase_out_threshold_end": float(result.phase_out_threshold_end),
        "excess_over_threshold": float(result.excess_over_threshold),
        "phase_out_range": float(result.phase_out_range),
        "phase_out_percentage": float(result.phase_out_percentage),
        "ot_credit_pre": float(result.ot_credit_pre),
        "tip_credit_pre": float(result.tip_credit_pre),
        "ot_credit_reduction": float(result.ot_credit_reduction),
        "tip_credit_reduction": float(result.tip_credit_reduction),
        "ot_credit_final": float(result.ot_credit_final),
        "tip_credit_final": float(result.tip_credit_final),
        "combined_credit_final": float(result.combined_credit_final),
        "is_fully_phased_out": result.is_fully_phased_out,
        "is_partially_phased_out": result.is_partially_phased_out,
        "is_no_phase_out": result.is_no_phase_out,
        "calculation_notes": result.calculation_notes,
    }


@mcp.tool()
async def estimate_employee_magi(
    ytd_wages: float,
    pay_periods_elapsed: int,
    total_pay_periods: int = 26,
    other_income: float = 0.0,
) -> dict:
    """
    Estimate an employee's annual MAGI based on year-to-date data.

    Uses linear projection to estimate full-year income. Useful for
    early warning about potential phase-out impacts.

    Args:
        ytd_wages: Year-to-date wages
        pay_periods_elapsed: Pay periods completed so far
        total_pay_periods: Total pay periods in year (26 biweekly, 24 semi-monthly)
        other_income: Estimated other income for the year

    Returns:
        Estimated annual MAGI
    """
    estimated = estimate_annual_magi(
        ytd_wages=Decimal(str(ytd_wages)),
        pay_periods_elapsed=pay_periods_elapsed,
        total_pay_periods=total_pay_periods,
        other_income=Decimal(str(other_income)),
    )

    return {
        "ytd_wages": ytd_wages,
        "pay_periods_elapsed": pay_periods_elapsed,
        "total_pay_periods": total_pay_periods,
        "projected_annual_wages": float(estimated - Decimal(str(other_income))),
        "estimated_annual_magi": float(estimated),
    }


@mcp.tool()
async def check_employee_phase_out_risk(
    current_magi_estimate: float,
    filing_status: Literal["single", "married_joint", "married_separate", "head_of_household"],
    tax_year: int = 2025,
) -> dict:
    """
    Check if an employee is at risk of MAGI phase-out.

    Returns risk assessment with percentage to threshold.

    Args:
        current_magi_estimate: Current estimated MAGI
        filing_status: Tax filing status
        tax_year: Tax year for threshold lookup

    Returns:
        Risk assessment with level and percentage
    """
    is_at_risk, pct_to_threshold, risk_level = check_phase_out_risk(
        current_magi=Decimal(str(current_magi_estimate)),
        filing_status=filing_status,
        tax_year=tax_year,
    )

    return {
        "current_magi_estimate": current_magi_estimate,
        "filing_status": filing_status,
        "tax_year": tax_year,
        "is_at_risk": is_at_risk,
        "percentage_to_threshold": float(pct_to_threshold),
        "risk_level": risk_level,
        "risk_description": {
            "none": "MAGI is well below phase-out threshold",
            "approaching": "MAGI is within 10% of phase-out threshold",
            "in_phase_out": "MAGI is in phase-out range, credits are being reduced",
            "fully_phased_out": "MAGI exceeds phase-out threshold, no credits available",
        }.get(risk_level, "Unknown"),
    }
