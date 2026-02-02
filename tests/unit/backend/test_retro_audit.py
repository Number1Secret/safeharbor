"""
Tests for Retro-Audit Report Service

Tests the risk assessment, discrepancy calculation, and recommendation logic.
"""

import types
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.services.retro_audit import (
    EmployeeAuditResult,
    RetroAuditReport,
    RetroAuditService,
    RiskLevel,
)


# ── Risk Assessment Tests ─────────────────────────────


class TestAssessRisk:
    """Test risk level determination based on discrepancy magnitude."""

    def _service(self):
        return RetroAuditService(db_session=None)

    def _result(self, total_discrepancy: Decimal) -> EmployeeAuditResult:
        return EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test Employee",
            total_discrepancy=total_discrepancy,
        )

    def test_zero_discrepancy_is_low(self):
        svc = self._service()
        result = self._result(Decimal("0"))
        assert svc._assess_risk(result) == RiskLevel.LOW

    def test_small_discrepancy_is_low(self):
        svc = self._service()
        result = self._result(Decimal("50"))
        assert svc._assess_risk(result) == RiskLevel.LOW

    def test_at_low_threshold_is_medium(self):
        svc = self._service()
        result = self._result(Decimal("100"))
        assert svc._assess_risk(result) == RiskLevel.MEDIUM

    def test_between_low_and_medium_is_medium(self):
        svc = self._service()
        result = self._result(Decimal("300"))
        assert svc._assess_risk(result) == RiskLevel.MEDIUM

    def test_at_medium_threshold_is_high(self):
        svc = self._service()
        result = self._result(Decimal("500"))
        assert svc._assess_risk(result) == RiskLevel.HIGH

    def test_between_medium_and_high_is_high(self):
        svc = self._service()
        result = self._result(Decimal("1000"))
        assert svc._assess_risk(result) == RiskLevel.HIGH

    def test_at_high_threshold_is_critical(self):
        svc = self._service()
        result = self._result(Decimal("2000"))
        assert svc._assess_risk(result) == RiskLevel.CRITICAL

    def test_large_discrepancy_is_critical(self):
        svc = self._service()
        result = self._result(Decimal("10000"))
        assert svc._assess_risk(result) == RiskLevel.CRITICAL

    def test_negative_discrepancy_uses_absolute_value(self):
        svc = self._service()
        result = self._result(Decimal("-2500"))
        assert svc._assess_risk(result) == RiskLevel.CRITICAL


# ── OT Premium Estimation Tests ───────────────────────


class TestEstimateSimpleOTPremium:
    """Test the simple 1.5x OT premium estimation."""

    def _service(self):
        return RetroAuditService(db_session=None)

    def test_basic_calculation(self):
        svc = self._service()
        calc = types.SimpleNamespace(
            hourly_rate=Decimal("20.00"),
            overtime_hours=Decimal("10"),
        )
        result = svc._estimate_simple_ot_premium(calc)
        # 20.00 * 0.5 * 10 = 100.00
        assert result == Decimal("100.00")

    def test_zero_hours(self):
        svc = self._service()
        calc = types.SimpleNamespace(
            hourly_rate=Decimal("15.00"),
            overtime_hours=Decimal("0"),
        )
        assert svc._estimate_simple_ot_premium(calc) == Decimal("0")

    def test_missing_rate(self):
        svc = self._service()
        calc = types.SimpleNamespace(hourly_rate=None, overtime_hours=Decimal("5"))
        assert svc._estimate_simple_ot_premium(calc) == Decimal("0")

    def test_missing_hours(self):
        svc = self._service()
        calc = types.SimpleNamespace(hourly_rate=Decimal("25.00"), overtime_hours=None)
        assert svc._estimate_simple_ot_premium(calc) == Decimal("0")


# ── Risk Factor Identification Tests ──────────────────


class TestIdentifyRiskFactors:
    """Test risk factor identification for employee audit results."""

    def _service(self):
        return RetroAuditService(db_session=None)

    def test_ot_under_calculation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            ot_premium_discrepancy=Decimal("500"),
        )
        factors = svc._identify_risk_factors(result, [])
        assert any("under-calculated" in f for f in factors)

    def test_ot_over_calculation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            ot_premium_discrepancy=Decimal("-300"),
        )
        factors = svc._identify_risk_factors(result, [])
        assert any("over-calculated" in f for f in factors)

    def test_unclaimed_tip_credit(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            tip_credit_discrepancy=Decimal("200"),
        )
        factors = svc._identify_risk_factors(result, [])
        assert any("tip credit" in f.lower() for f in factors)

    def test_phase_out_factor(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            phase_out_percentage=Decimal("25"),
        )
        factors = svc._identify_risk_factors(result, [])
        assert any("phase-out" in f.lower() for f in factors)

    def test_missing_ttoc(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            ttoc_code=None,
        )
        factors = svc._identify_risk_factors(result, [])
        assert any("ttoc" in f.lower() for f in factors)


# ── Recommendation Generation Tests ───────────────────


class TestGenerateRecommendations:
    """Test recommendation generation."""

    def _service(self):
        return RetroAuditService(db_session=None)

    def test_high_risk_gets_priority_recommendation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            risk_level=RiskLevel.HIGH,
        )
        recs = svc._generate_recommendations(result)
        assert any("priority" in r.lower() for r in recs)

    def test_critical_risk_gets_priority_recommendation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            risk_level=RiskLevel.CRITICAL,
        )
        recs = svc._generate_recommendations(result)
        assert any("priority" in r.lower() for r in recs)

    def test_ot_discrepancy_gets_weighted_rate_recommendation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            ot_premium_discrepancy=Decimal("100"),
        )
        recs = svc._generate_recommendations(result)
        assert any("weighted average" in r.lower() for r in recs)

    def test_no_ttoc_gets_classification_recommendation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            ttoc_code=None,
        )
        recs = svc._generate_recommendations(result)
        assert any("ttoc" in r.lower() for r in recs)

    def test_high_phase_out_gets_magi_review_recommendation(self):
        svc = self._service()
        result = EmployeeAuditResult(
            employee_id=uuid4(),
            employee_name="Test",
            phase_out_percentage=Decimal("60"),
        )
        recs = svc._generate_recommendations(result)
        assert any("magi" in r.lower() for r in recs)


# ── Top Issues Identification Tests ───────────────────


class TestIdentifyTopIssues:
    """Test top issues identification from full report."""

    def _service(self):
        return RetroAuditService(db_session=None)

    def test_systematic_ot_error_flagged(self):
        svc = self._service()
        report = RetroAuditReport(
            organization_id=uuid4(),
            organization_name="Test",
            tax_year=2025,
            report_date="2025-06-01",
            generated_at="2025-06-01T00:00:00",
            ot_premium_total_discrepancy=Decimal("1500"),
            risk_distribution={"low": 0, "medium": 0, "high": 0, "critical": 0},
        )
        issues = svc._identify_top_issues(report)
        assert any(i["type"] == "systematic_ot_error" for i in issues)

    def test_unclaimed_tips_flagged(self):
        svc = self._service()
        report = RetroAuditReport(
            organization_id=uuid4(),
            organization_name="Test",
            tax_year=2025,
            report_date="2025-06-01",
            generated_at="2025-06-01T00:00:00",
            tip_credit_total_discrepancy=Decimal("800"),
            risk_distribution={"low": 0, "medium": 0, "high": 0, "critical": 0},
        )
        issues = svc._identify_top_issues(report)
        assert any(i["type"] == "unclaimed_tip_credits" for i in issues)

    def test_high_risk_employees_flagged(self):
        svc = self._service()
        report = RetroAuditReport(
            organization_id=uuid4(),
            organization_name="Test",
            tax_year=2025,
            report_date="2025-06-01",
            generated_at="2025-06-01T00:00:00",
            risk_distribution={"low": 5, "medium": 2, "high": 3, "critical": 1},
        )
        issues = svc._identify_top_issues(report)
        assert any(i["type"] == "high_risk_employees" for i in issues)

    def test_no_issues_when_below_thresholds(self):
        svc = self._service()
        report = RetroAuditReport(
            organization_id=uuid4(),
            organization_name="Test",
            tax_year=2025,
            report_date="2025-06-01",
            generated_at="2025-06-01T00:00:00",
            ot_premium_total_discrepancy=Decimal("50"),
            tip_credit_total_discrepancy=Decimal("100"),
            risk_distribution={"low": 10, "medium": 0, "high": 0, "critical": 0},
        )
        issues = svc._identify_top_issues(report)
        assert len(issues) == 0
