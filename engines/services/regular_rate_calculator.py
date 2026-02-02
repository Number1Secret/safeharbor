"""
Regular Rate Calculator

Pure calculation logic for FLSA Section 7 Regular Rate of Pay.
Implements 29 CFR § 778.109 methodology.
"""

from decimal import ROUND_HALF_UP, Decimal

from engines.schemas.premium_engine import RegularRateInput, RegularRateOutput

# Federal minimum wage as of 2024
FEDERAL_MINIMUM_WAGE = Decimal("7.25")


def calculate_regular_rate(input_data: RegularRateInput) -> RegularRateOutput:
    """
    Calculate FLSA Section 7 Regular Rate of Pay.

    The regular rate is a weighted average hourly rate that includes
    all remuneration for employment except specific exclusions under
    FLSA Section 207(e).

    Algorithm:
    1. Calculate total hours (regular + OT + state OT + double-time)
    2. Sum all includable compensation
    3. Divide total compensation by total hours = Regular Rate
    4. Apply federal minimum wage floor
    5. Calculate overtime premium (0.5x × Regular Rate × OT Hours)
    6. Exclude double-time from OBBB qualified amount

    Reference: 29 CFR § 778.109
    """
    notes: list[str] = []

    # Step 1: Calculate total hours
    total_hours = (
        input_data.regular_hours
        + input_data.overtime_hours
        + input_data.state_overtime_hours
        + input_data.double_time_hours
    )

    if total_hours == 0:
        # Edge case: no hours worked
        return RegularRateOutput(
            employee_id=input_data.employee_id,
            period_start=input_data.period_start,
            period_end=input_data.period_end,
            total_hours=Decimal("0"),
            total_compensation=Decimal("0"),
            regular_rate=input_data.hourly_rate,
            overtime_hours_qualified=Decimal("0"),
            overtime_premium=Decimal("0"),
            qualified_ot_premium=Decimal("0"),
            regular_rate_components={},
            excluded_components={},
            minimum_wage_applied=False,
            calculation_notes=["No hours worked in period"],
        )

    # Step 2: Calculate base wages and includable compensation
    base_wages = input_data.hourly_rate * input_data.regular_hours

    # Includable compensation components
    includable = {
        "base_wages": float(base_wages),
        "shift_differentials": float(input_data.shift_differentials),
        "non_discretionary_bonuses": float(input_data.non_discretionary_bonuses),
        "commissions": float(input_data.commissions),
        "piece_rate_earnings": float(input_data.piece_rate_earnings),
    }

    total_compensation = (
        base_wages
        + input_data.shift_differentials
        + input_data.non_discretionary_bonuses
        + input_data.commissions
        + input_data.piece_rate_earnings
    )

    # Excluded components (for documentation)
    excluded = {
        "discretionary_bonuses": float(input_data.discretionary_bonuses),
        "gifts": float(input_data.gifts),
        "expense_reimbursements": float(input_data.expense_reimbursements),
        "premium_pay_already_counted": float(input_data.premium_pay_already_counted),
    }

    # Step 3: Calculate regular rate
    regular_rate = (total_compensation / total_hours).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    # Step 4: Apply federal minimum wage floor
    minimum_wage_applied = False
    if regular_rate < FEDERAL_MINIMUM_WAGE:
        notes.append(
            f"Regular rate {regular_rate} below minimum wage; using {FEDERAL_MINIMUM_WAGE}"
        )
        regular_rate = FEDERAL_MINIMUM_WAGE
        minimum_wage_applied = True

    # Step 5: Calculate overtime premium
    # OT premium is 0.5x the regular rate for each OT hour
    # (The other 1.0x is already included in total compensation)
    federal_ot_hours = input_data.overtime_hours
    state_ot_hours = input_data.state_overtime_hours

    # Total OT hours for premium calculation (federal + state, but not double-time)
    total_ot_hours = federal_ot_hours + state_ot_hours

    overtime_premium = (regular_rate * Decimal("0.5") * total_ot_hours).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Step 6: OBBB qualified amount excludes double-time hours
    # Per OBBB, only the 0.5x premium on regular overtime qualifies
    # Double-time (usually >12 hours/day in CA) is excluded
    overtime_hours_qualified = total_ot_hours  # Double-time already excluded from this
    qualified_ot_premium = overtime_premium  # All non-double-time OT premium qualifies

    if input_data.double_time_hours > 0:
        notes.append(
            f"Excluded {input_data.double_time_hours} double-time hours from OBBB qualified amount"
        )

    return RegularRateOutput(
        employee_id=input_data.employee_id,
        period_start=input_data.period_start,
        period_end=input_data.period_end,
        total_hours=total_hours,
        total_compensation=total_compensation,
        regular_rate=regular_rate,
        overtime_hours_qualified=overtime_hours_qualified,
        overtime_premium=overtime_premium,
        qualified_ot_premium=qualified_ot_premium,
        regular_rate_components=includable,
        excluded_components=excluded,
        minimum_wage_applied=minimum_wage_applied,
        calculation_notes=notes,
    )


def calculate_tip_credit(
    total_tips: Decimal,
    ttoc_code: str | None,
    hours_in_tipped_role: Decimal,
    hours_in_non_tipped_role: Decimal,
) -> tuple[Decimal, bool, str | None]:
    """
    Calculate qualified tips for OBBB exemption.

    Tips only qualify if:
    1. Employee is in a qualifying TTOC occupation
    2. Tips are properly documented

    For dual-job employees, tips are apportioned based on time in tipped role.

    Returns:
        Tuple of (qualified_tips, is_eligible, ineligibility_reason)
    """
    # Check TTOC eligibility
    if not ttoc_code:
        return Decimal("0"), False, "No TTOC classification assigned"

    # Calculate apportionment for dual-job employees
    total_hours = hours_in_tipped_role + hours_in_non_tipped_role

    if total_hours == 0:
        return Decimal("0"), False, "No hours worked"

    if hours_in_non_tipped_role > 0:
        # Dual-job employee: apportion tips based on time in tipped role
        tipped_percentage = hours_in_tipped_role / total_hours
        qualified_tips = (total_tips * tipped_percentage).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        # Full-time tipped employee
        qualified_tips = total_tips

    return qualified_tips, True, None
