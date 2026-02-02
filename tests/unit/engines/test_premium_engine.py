"""
Premium Engine Unit Tests

Tests for FLSA Section 7 Regular Rate calculation.
Based on DOL test cases and PRD examples.
"""

from decimal import Decimal

import pytest

from engines.schemas.premium_engine import RegularRateInput
from engines.services.regular_rate_calculator import calculate_regular_rate


class TestRegularRateCalculation:
    """Test FLSA Regular Rate calculation."""

    def test_simple_hourly_employee_no_overtime(self):
        """Test simple case: hourly employee with no overtime."""
        input_data = RegularRateInput(
            employee_id="emp-001",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("0"),
            hourly_rate=Decimal("15.00"),
        )

        result = calculate_regular_rate(input_data)

        assert result.total_hours == Decimal("40")
        assert result.regular_rate == Decimal("15.0000")
        assert result.overtime_premium == Decimal("0.00")
        assert result.qualified_ot_premium == Decimal("0.00")

    def test_simple_overtime(self):
        """Test basic overtime calculation."""
        input_data = RegularRateInput(
            employee_id="emp-002",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("5"),
            hourly_rate=Decimal("20.00"),
        )

        result = calculate_regular_rate(input_data)

        assert result.total_hours == Decimal("45")
        assert result.regular_rate == Decimal("20.0000")  # No other comp, so same as hourly
        # OT premium = $20.00 × 0.5 × 5 hours = $50.00
        assert result.overtime_premium == Decimal("50.00")
        assert result.qualified_ot_premium == Decimal("50.00")

    def test_weighted_average_multiple_rates(self):
        """
        Test PRD Example (Section 2.3.1):
        Employee works 44 hours at varying rates:
        - 24 hours at $15/hr = $360
        - 20 hours at $18/hr = $360
        - Total: $720 / 44 hours = $16.36/hr Regular Rate
        - OT Premium: $16.36 × 0.5 × 4 hours = $32.73
        """
        # Simulate this with shift differentials
        # Base: 44 hours at $15 = $660, plus $60 differential = $720
        input_data = RegularRateInput(
            employee_id="emp-003",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("4"),
            hourly_rate=Decimal("15.00"),
            shift_differentials=Decimal("60.00"),  # Extra for bartending shifts
        )

        result = calculate_regular_rate(input_data)

        assert result.total_hours == Decimal("44")
        # Regular rate = $720 / 44 = $16.3636...
        assert result.regular_rate == Decimal("16.3636")
        # OT premium = $16.36 × 0.5 × 4 = $32.73
        assert result.overtime_premium == Decimal("32.73")

    def test_non_discretionary_bonus_included(self):
        """Test that non-discretionary bonuses are included in regular rate."""
        input_data = RegularRateInput(
            employee_id="emp-004",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("10"),
            hourly_rate=Decimal("20.00"),
            non_discretionary_bonuses=Decimal("100.00"),  # Production bonus
        )

        result = calculate_regular_rate(input_data)

        # Total comp = $800 (wages) + $100 (bonus) = $900
        # Total hours = 50
        # Regular rate = $900 / 50 = $18.00
        assert result.regular_rate == Decimal("18.0000")
        # OT premium = $18.00 × 0.5 × 10 = $90.00
        assert result.overtime_premium == Decimal("90.00")

    def test_discretionary_bonus_excluded(self):
        """Test that discretionary bonuses are excluded from regular rate."""
        input_data = RegularRateInput(
            employee_id="emp-005",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("10"),
            hourly_rate=Decimal("20.00"),
            discretionary_bonuses=Decimal("500.00"),  # Holiday gift
        )

        result = calculate_regular_rate(input_data)

        # Discretionary bonus should NOT affect regular rate
        # Total comp = $800 (wages only)
        # Regular rate = $800 / 50 = $16.00
        assert result.regular_rate == Decimal("16.0000")
        assert result.excluded_components["discretionary_bonuses"] == 500.00

    def test_minimum_wage_floor(self):
        """Test that federal minimum wage is applied as floor."""
        input_data = RegularRateInput(
            employee_id="emp-006",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("0"),
            hourly_rate=Decimal("5.00"),  # Below minimum wage
        )

        result = calculate_regular_rate(input_data)

        # Should be raised to federal minimum wage
        assert result.regular_rate == Decimal("7.25")
        assert result.minimum_wage_applied is True
        assert "minimum wage" in result.calculation_notes[0].lower()

    def test_double_time_excluded_from_obbb(self):
        """Test that double-time hours are excluded from OBBB qualified amount."""
        input_data = RegularRateInput(
            employee_id="emp-007",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("4"),  # Regular OT
            double_time_hours=Decimal("2"),  # Double-time (excluded)
            hourly_rate=Decimal("20.00"),
        )

        result = calculate_regular_rate(input_data)

        assert result.total_hours == Decimal("46")
        # Regular OT qualifies, double-time does not
        assert result.overtime_hours_qualified == Decimal("4")
        # OT premium calculated on regular OT only
        # But the regular rate is based on all hours

    def test_commissions_included(self):
        """Test that commissions are included in regular rate."""
        input_data = RegularRateInput(
            employee_id="emp-008",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("40"),
            overtime_hours=Decimal("5"),
            hourly_rate=Decimal("10.00"),
            commissions=Decimal("500.00"),
        )

        result = calculate_regular_rate(input_data)

        # Total comp = $400 (wages) + $500 (commissions) = $900
        # Total hours = 45
        # Regular rate = $900 / 45 = $20.00
        assert result.regular_rate == Decimal("20.0000")
        assert result.regular_rate_components["commissions"] == 500.00

    def test_zero_hours_edge_case(self):
        """Test handling of zero hours worked."""
        input_data = RegularRateInput(
            employee_id="emp-009",
            period_start="2025-01-01",
            period_end="2025-01-07",
            regular_hours=Decimal("0"),
            overtime_hours=Decimal("0"),
            hourly_rate=Decimal("15.00"),
        )

        result = calculate_regular_rate(input_data)

        assert result.total_hours == Decimal("0")
        assert result.regular_rate == Decimal("15.00")  # Falls back to hourly rate
        assert result.overtime_premium == Decimal("0.00")


class TestTipCreditCalculation:
    """Test tip credit calculation."""

    def test_simple_tip_credit(self):
        """Test basic tip credit for tipped employee."""
        from engines.services.regular_rate_calculator import calculate_tip_credit

        qualified, eligible, reason = calculate_tip_credit(
            total_tips=Decimal("500.00"),
            ttoc_code="12401",  # Server
            hours_in_tipped_role=Decimal("40"),
            hours_in_non_tipped_role=Decimal("0"),
        )

        assert eligible is True
        assert qualified == Decimal("500.00")
        assert reason is None

    def test_no_ttoc_ineligible(self):
        """Test that employees without TTOC are ineligible."""
        from engines.services.regular_rate_calculator import calculate_tip_credit

        qualified, eligible, reason = calculate_tip_credit(
            total_tips=Decimal("500.00"),
            ttoc_code=None,
            hours_in_tipped_role=Decimal("40"),
            hours_in_non_tipped_role=Decimal("0"),
        )

        assert eligible is False
        assert qualified == Decimal("0")
        assert "TTOC" in reason

    def test_dual_job_apportionment(self):
        """Test tip apportionment for dual-job employees."""
        from engines.services.regular_rate_calculator import calculate_tip_credit

        # 30 hours tipped, 10 hours non-tipped = 75% tipped
        qualified, eligible, reason = calculate_tip_credit(
            total_tips=Decimal("400.00"),
            ttoc_code="12401",
            hours_in_tipped_role=Decimal("30"),
            hours_in_non_tipped_role=Decimal("10"),
        )

        assert eligible is True
        # 75% of $400 = $300
        assert qualified == Decimal("300.00")
