"""
Premium Engine MCP Tool

FLSA Section 7 Regular Rate calculation exposed as an MCP tool.
"""

from decimal import Decimal

from fastmcp import FastMCP

from engines.schemas.premium_engine import (
    RegularRateInput,
    RegularRateOutput,
    TipCreditInput,
    TipCreditOutput,
)
from engines.services.regular_rate_calculator import calculate_regular_rate, calculate_tip_credit

# Initialize MCP server (will be started from server.py)
mcp = FastMCP("SafeHarbor Premium Engine")


@mcp.tool()
async def calculate_flsa_regular_rate(
    employee_id: str,
    period_start: str,
    period_end: str,
    regular_hours: float,
    hourly_rate: float,
    overtime_hours: float = 0.0,
    state_overtime_hours: float = 0.0,
    double_time_hours: float = 0.0,
    shift_differentials: float = 0.0,
    non_discretionary_bonuses: float = 0.0,
    commissions: float = 0.0,
    piece_rate_earnings: float = 0.0,
    discretionary_bonuses: float = 0.0,
    gifts: float = 0.0,
    expense_reimbursements: float = 0.0,
    premium_pay_already_counted: float = 0.0,
) -> dict:
    """
    Calculate FLSA Section 7 Regular Rate of Pay.

    The regular rate is a weighted average that includes all remuneration
    for employment except specific exclusions under FLSA Section 207(e).

    This calculation is critical for OBBB compliance because the qualified
    overtime premium is calculated as 0.5x the Regular Rate, not 0.5x the
    base hourly rate.

    Args:
        employee_id: Unique employee identifier
        period_start: Period start date (YYYY-MM-DD)
        period_end: Period end date (YYYY-MM-DD)
        regular_hours: Non-overtime hours worked
        hourly_rate: Primary hourly rate
        overtime_hours: Federal overtime hours (>40/week)
        state_overtime_hours: State-specific OT (e.g., CA daily OT)
        double_time_hours: Double-time hours (excluded from OBBB)
        shift_differentials: Shift differential pay
        non_discretionary_bonuses: Production/attendance bonuses
        commissions: Commission earnings
        piece_rate_earnings: Piece-rate pay
        discretionary_bonuses: Holiday/year-end gifts (excluded)
        gifts: Non-production gifts (excluded)
        expense_reimbursements: Travel/uniform reimbursements (excluded)
        premium_pay_already_counted: Premiums credited to OT (excluded)

    Returns:
        Dictionary containing regular rate, OT premium, and breakdown

    Example:
        Employee works 44 hours at varying rates:
        - 24 hours at $15/hr = $360
        - 20 hours at $18/hr = $360
        - Total: $720 / 44 hours = $16.36/hr Regular Rate
        - OT Premium: $16.36 × 0.5 × 4 hours = $32.73
    """
    # Convert floats to Decimal for precision
    input_data = RegularRateInput(
        employee_id=employee_id,
        period_start=period_start,
        period_end=period_end,
        regular_hours=Decimal(str(regular_hours)),
        overtime_hours=Decimal(str(overtime_hours)),
        state_overtime_hours=Decimal(str(state_overtime_hours)),
        double_time_hours=Decimal(str(double_time_hours)),
        hourly_rate=Decimal(str(hourly_rate)),
        shift_differentials=Decimal(str(shift_differentials)),
        non_discretionary_bonuses=Decimal(str(non_discretionary_bonuses)),
        commissions=Decimal(str(commissions)),
        piece_rate_earnings=Decimal(str(piece_rate_earnings)),
        discretionary_bonuses=Decimal(str(discretionary_bonuses)),
        gifts=Decimal(str(gifts)),
        expense_reimbursements=Decimal(str(expense_reimbursements)),
        premium_pay_already_counted=Decimal(str(premium_pay_already_counted)),
    )

    result = calculate_regular_rate(input_data)

    # Convert to dict with float values for JSON serialization
    return {
        "employee_id": result.employee_id,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "total_hours": float(result.total_hours),
        "total_compensation": float(result.total_compensation),
        "regular_rate": float(result.regular_rate),
        "overtime_hours_qualified": float(result.overtime_hours_qualified),
        "overtime_premium": float(result.overtime_premium),
        "qualified_ot_premium": float(result.qualified_ot_premium),
        "regular_rate_components": result.regular_rate_components,
        "excluded_components": result.excluded_components,
        "minimum_wage_applied": result.minimum_wage_applied,
        "calculation_notes": result.calculation_notes,
    }


@mcp.tool()
async def calculate_qualified_tips(
    employee_id: str,
    period_start: str,
    period_end: str,
    cash_tips: float = 0.0,
    charged_tips: float = 0.0,
    tip_pool_contribution: float = 0.0,
    tip_pool_distribution: float = 0.0,
    ttoc_code: str | None = None,
    hours_in_tipped_role: float = 0.0,
    hours_in_non_tipped_role: float = 0.0,
) -> dict:
    """
    Calculate qualified tips for OBBB exemption.

    Tips only qualify if the employee is in a Treasury Tipped Occupation
    Code (TTOC) classified role. For dual-job employees, tips are
    apportioned based on time spent in the tipped role.

    Args:
        employee_id: Unique employee identifier
        period_start: Period start date (YYYY-MM-DD)
        period_end: Period end date (YYYY-MM-DD)
        cash_tips: Cash tips received
        charged_tips: Credit card tips received
        tip_pool_contribution: Tips contributed to pool
        tip_pool_distribution: Tips received from pool
        ttoc_code: Treasury Tipped Occupation Code
        hours_in_tipped_role: Hours worked in tipped position
        hours_in_non_tipped_role: Hours in non-tipped position

    Returns:
        Dictionary containing qualified tips and eligibility status
    """
    # Calculate total tips
    total_tips = Decimal(str(cash_tips)) + Decimal(str(charged_tips))
    net_pool = Decimal(str(tip_pool_distribution)) - Decimal(str(tip_pool_contribution))
    total_tips += net_pool

    # Calculate qualified amount
    qualified_tips, is_eligible, reason = calculate_tip_credit(
        total_tips=total_tips,
        ttoc_code=ttoc_code,
        hours_in_tipped_role=Decimal(str(hours_in_tipped_role)),
        hours_in_non_tipped_role=Decimal(str(hours_in_non_tipped_role)),
    )

    total_hours = hours_in_tipped_role + hours_in_non_tipped_role
    tipped_percentage = (
        hours_in_tipped_role / total_hours if total_hours > 0 else Decimal("0")
    )

    return {
        "employee_id": employee_id,
        "period_start": period_start,
        "period_end": period_end,
        "total_tips": float(total_tips),
        "qualified_tips": float(qualified_tips),
        "cash_tips": cash_tips,
        "charged_tips": charged_tips,
        "net_pool_adjustment": float(net_pool),
        "tipped_role_percentage": float(tipped_percentage),
        "apportionment_applied": hours_in_non_tipped_role > 0,
        "is_eligible": is_eligible,
        "ineligibility_reason": reason,
    }
