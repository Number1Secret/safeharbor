"""
Phase-Out Filter Unit Tests

Tests for MAGI-based phase-out calculation.
"""

from decimal import Decimal

import pytest

from engines.schemas.phase_out import PhaseOutInput
from engines.services.magi_tracker import (
    calculate_magi,
    calculate_phase_out,
    check_phase_out_risk,
    estimate_annual_magi,
    get_thresholds,
)


class TestMAGICalculation:
    """Test MAGI calculation."""

    def test_simple_magi(self):
        """Test basic MAGI calculation with wages only."""
        input_data = PhaseOutInput(
            employee_id="emp-001",
            tax_year=2025,
            wages=Decimal("80000"),
            filing_status="single",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        magi = calculate_magi(input_data)
        assert magi == Decimal("80000")

    def test_magi_with_all_components(self):
        """Test MAGI with all income sources."""
        input_data = PhaseOutInput(
            employee_id="emp-002",
            tax_year=2025,
            wages=Decimal("70000"),
            self_employment_income=Decimal("10000"),
            investment_income=Decimal("5000"),
            other_income=Decimal("2000"),
            above_the_line_deductions=Decimal("2000"),
            filing_status="single",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        magi = calculate_magi(input_data)
        # 70000 + 10000 + 5000 + 2000 - 2000 = 85000
        assert magi == Decimal("85000")


class TestPhaseOutThresholds:
    """Test phase-out threshold lookup."""

    def test_single_thresholds(self):
        """Test single filer thresholds."""
        start, end = get_thresholds(2025, "single")
        assert start == Decimal("75000")
        assert end == Decimal("100000")

    def test_married_joint_thresholds(self):
        """Test married filing jointly thresholds."""
        start, end = get_thresholds(2025, "married_joint")
        assert start == Decimal("150000")
        assert end == Decimal("200000")

    def test_head_of_household_thresholds(self):
        """Test head of household thresholds."""
        start, end = get_thresholds(2025, "head_of_household")
        assert start == Decimal("112500")
        assert end == Decimal("150000")

    def test_unknown_year_fallback(self):
        """Test that unknown year falls back to 2025."""
        start, end = get_thresholds(2030, "single")
        assert start == Decimal("75000")
        assert end == Decimal("100000")


class TestPhaseOutCalculation:
    """Test phase-out calculation."""

    def test_no_phase_out_below_threshold(self):
        """Test no phase-out when MAGI is below threshold."""
        input_data = PhaseOutInput(
            employee_id="emp-001",
            tax_year=2025,
            wages=Decimal("60000"),
            filing_status="single",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        result = calculate_phase_out(input_data)

        assert result.is_no_phase_out is True
        assert result.is_partially_phased_out is False
        assert result.is_fully_phased_out is False
        assert result.phase_out_percentage == Decimal("0")
        assert result.ot_credit_final == Decimal("1000")
        assert result.tip_credit_final == Decimal("500")

    def test_partial_phase_out(self):
        """Test partial phase-out in the middle of the range."""
        input_data = PhaseOutInput(
            employee_id="emp-002",
            tax_year=2025,
            wages=Decimal("87500"),  # Midpoint for single
            filing_status="single",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        result = calculate_phase_out(input_data)

        assert result.is_no_phase_out is False
        assert result.is_partially_phased_out is True
        assert result.is_fully_phased_out is False
        # $87,500 - $75,000 = $12,500 over threshold
        # $12,500 / $25,000 range = 50%
        assert result.phase_out_percentage == Decimal("50.00")
        # 50% of $1000 = $500 reduction
        assert result.ot_credit_reduction == Decimal("500.00")
        assert result.ot_credit_final == Decimal("500.00")
        # 50% of $500 = $250 reduction
        assert result.tip_credit_reduction == Decimal("250.00")
        assert result.tip_credit_final == Decimal("250.00")

    def test_full_phase_out(self):
        """Test full phase-out above threshold end."""
        input_data = PhaseOutInput(
            employee_id="emp-003",
            tax_year=2025,
            wages=Decimal("110000"),  # Above $100k end
            filing_status="single",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        result = calculate_phase_out(input_data)

        assert result.is_no_phase_out is False
        assert result.is_partially_phased_out is False
        assert result.is_fully_phased_out is True
        assert result.phase_out_percentage == Decimal("100")
        assert result.ot_credit_final == Decimal("0.00")
        assert result.tip_credit_final == Decimal("0.00")
        assert result.combined_credit_final == Decimal("0.00")

    def test_married_joint_higher_thresholds(self):
        """Test married filing jointly has higher thresholds."""
        input_data = PhaseOutInput(
            employee_id="emp-004",
            tax_year=2025,
            wages=Decimal("100000"),  # Would be phased out for single
            filing_status="married_joint",
            ot_credit_pre_phase_out=Decimal("1000"),
            tip_credit_pre_phase_out=Decimal("500"),
        )

        result = calculate_phase_out(input_data)

        # $100k is below $150k threshold for married joint
        assert result.is_no_phase_out is True
        assert result.ot_credit_final == Decimal("1000")
        assert result.tip_credit_final == Decimal("500")


class TestPhaseOutRiskCheck:
    """Test phase-out risk assessment."""

    def test_no_risk(self):
        """Test employee well below threshold."""
        is_at_risk, pct, level = check_phase_out_risk(
            current_magi=Decimal("50000"),
            filing_status="single",
            tax_year=2025,
        )

        assert is_at_risk is False
        assert level == "none"

    def test_approaching_risk(self):
        """Test employee approaching threshold (within 10%)."""
        is_at_risk, pct, level = check_phase_out_risk(
            current_magi=Decimal("70000"),  # 93% of $75k threshold
            filing_status="single",
            tax_year=2025,
        )

        assert is_at_risk is True
        assert level == "approaching"

    def test_in_phase_out(self):
        """Test employee in phase-out range."""
        is_at_risk, pct, level = check_phase_out_risk(
            current_magi=Decimal("85000"),
            filing_status="single",
            tax_year=2025,
        )

        assert is_at_risk is True
        assert level == "in_phase_out"

    def test_fully_phased_out(self):
        """Test employee fully phased out."""
        is_at_risk, pct, level = check_phase_out_risk(
            current_magi=Decimal("120000"),
            filing_status="single",
            tax_year=2025,
        )

        assert is_at_risk is True
        assert level == "fully_phased_out"


class TestMAGIEstimation:
    """Test annual MAGI estimation."""

    def test_midyear_projection(self):
        """Test projecting annual MAGI from YTD data."""
        # 6 months in, earned $40k, project to $80k
        estimated = estimate_annual_magi(
            ytd_wages=Decimal("40000"),
            pay_periods_elapsed=13,  # Biweekly, half year
            total_pay_periods=26,
            other_income=Decimal("0"),
        )

        # $40k / 13 * 26 = ~$80k
        assert estimated == Decimal("80000")

    def test_with_other_income(self):
        """Test projection with other income."""
        estimated = estimate_annual_magi(
            ytd_wages=Decimal("30000"),
            pay_periods_elapsed=12,  # Semi-monthly, half year
            total_pay_periods=24,
            other_income=Decimal("10000"),  # Investment income
        )

        # Projected wages: $30k / 12 * 24 = $60k
        # Plus other income: $10k
        # Total: $70k
        assert estimated == Decimal("70000")

    def test_zero_periods_edge_case(self):
        """Test handling of zero pay periods."""
        estimated = estimate_annual_magi(
            ytd_wages=Decimal("0"),
            pay_periods_elapsed=0,
            total_pay_periods=26,
            other_income=Decimal("5000"),
        )

        # Only other income
        assert estimated == Decimal("5000")
