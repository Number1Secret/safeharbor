"""
Retro-Audit Report Service

Analyzes 2025 payroll data to identify discrepancies between
estimated and correct OBBB tax exemption values.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmployeeAuditResult(BaseModel):
    """Per-employee audit finding."""
    employee_id: UUID
    employee_name: str
    ttoc_code: str | None = None
    ttoc_title: str | None = None

    # Overtime premium analysis
    estimated_ot_premium: Decimal = Decimal("0")
    correct_ot_premium: Decimal = Decimal("0")
    ot_premium_discrepancy: Decimal = Decimal("0")

    # Tip credit analysis
    estimated_tip_credit: Decimal = Decimal("0")
    correct_tip_credit: Decimal = Decimal("0")
    tip_credit_discrepancy: Decimal = Decimal("0")

    # Phase-out impact
    magi_estimate: Decimal | None = None
    phase_out_percentage: Decimal = Decimal("0")

    # Total impact
    total_estimated: Decimal = Decimal("0")
    total_correct: Decimal = Decimal("0")
    total_discrepancy: Decimal = Decimal("0")

    # Risk
    risk_level: RiskLevel = RiskLevel.LOW
    risk_factors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RetroAuditReport(BaseModel):
    """Full retro-audit report."""
    organization_id: UUID
    organization_name: str
    tax_year: int
    report_date: date
    generated_at: datetime

    # Summary
    total_employees_analyzed: int = 0
    employees_with_discrepancies: int = 0
    employees_at_risk: int = 0

    # Aggregate discrepancies
    total_estimated_credits: Decimal = Decimal("0")
    total_correct_credits: Decimal = Decimal("0")
    total_discrepancy: Decimal = Decimal("0")
    potential_penalty_exposure: Decimal = Decimal("0")

    # Breakdown by type
    ot_premium_total_discrepancy: Decimal = Decimal("0")
    tip_credit_total_discrepancy: Decimal = Decimal("0")
    phase_out_total_impact: Decimal = Decimal("0")

    # Risk distribution
    risk_distribution: dict[str, int] = Field(default_factory=dict)

    # Per-employee results
    employee_results: list[EmployeeAuditResult] = Field(default_factory=list)

    # Top issues
    top_issues: list[dict[str, Any]] = Field(default_factory=list)


class RetroAuditService:
    """
    Generates retro-audit reports comparing estimated vs correct
    OBBB tax exemption values for a given organization and period.
    """

    # IRS penalty rates for incorrect reporting
    UNDERPAYMENT_PENALTY_RATE = Decimal("0.05")  # 5% per year
    ACCURACY_PENALTY_RATE = Decimal("0.20")  # 20% substantial understatement

    # Discrepancy thresholds
    DISCREPANCY_THRESHOLD_LOW = Decimal("100")
    DISCREPANCY_THRESHOLD_MEDIUM = Decimal("500")
    DISCREPANCY_THRESHOLD_HIGH = Decimal("2000")

    def __init__(self, db_session):
        self.db = db_session

    async def generate_report(
        self,
        organization_id: UUID,
        tax_year: int = 2025,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> RetroAuditReport:
        """
        Generate a retro-audit report for an organization.

        Args:
            organization_id: Organization to audit
            tax_year: Tax year to analyze
            period_start: Optional start date (defaults to Jan 1)
            period_end: Optional end date (defaults to Dec 31)

        Returns:
            RetroAuditReport with per-employee analysis
        """
        if not period_start:
            period_start = date(tax_year, 1, 1)
        if not period_end:
            period_end = date(tax_year, 12, 31)

        # Fetch organization
        org = await self._get_organization(organization_id)

        report = RetroAuditReport(
            organization_id=organization_id,
            organization_name=org.get("name", "Unknown"),
            tax_year=tax_year,
            report_date=date.today(),
            generated_at=datetime.utcnow(),
        )

        # Fetch employees with their calculation history
        employees = await self._get_employees_with_calculations(
            organization_id, period_start, period_end
        )

        for emp in employees:
            result = await self._audit_employee(emp, period_start, period_end)
            report.employee_results.append(result)
            report.total_employees_analyzed += 1

            if result.total_discrepancy != Decimal("0"):
                report.employees_with_discrepancies += 1
                report.total_discrepancy += result.total_discrepancy
                report.ot_premium_total_discrepancy += result.ot_premium_discrepancy
                report.tip_credit_total_discrepancy += result.tip_credit_discrepancy

            if result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                report.employees_at_risk += 1

            report.total_estimated_credits += result.total_estimated
            report.total_correct_credits += result.total_correct

        # Calculate penalty exposure
        underpayment = max(report.total_discrepancy, Decimal("0"))
        report.potential_penalty_exposure = (
            underpayment * self.UNDERPAYMENT_PENALTY_RATE
            + underpayment * self.ACCURACY_PENALTY_RATE
        )

        # Build risk distribution
        risk_counts: dict[str, int] = {level.value: 0 for level in RiskLevel}
        for result in report.employee_results:
            risk_counts[result.risk_level.value] += 1
        report.risk_distribution = risk_counts

        # Identify top issues
        report.top_issues = self._identify_top_issues(report)

        return report

    async def _get_organization(self, org_id: UUID) -> dict:
        """Fetch organization details."""
        from sqlalchemy import select
        from backend.models.organization import Organization

        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = result.scalar_one_or_none()
        if not org:
            return {"name": "Unknown"}
        return {"name": org.name, "ein": org.ein, "settings": org.settings}

    async def _get_employees_with_calculations(
        self,
        org_id: UUID,
        period_start: date,
        period_end: date,
    ) -> list[dict]:
        """Fetch employees and their calculation history for the period."""
        from sqlalchemy import select
        from backend.models.employee import Employee
        from backend.models.employee_calculation import EmployeeCalculation
        from backend.models.calculation_run import CalculationRun

        # Get employees
        emp_result = await self.db.execute(
            select(Employee).where(Employee.organization_id == org_id)
        )
        employees = emp_result.scalars().all()

        employee_data = []
        for emp in employees:
            # Get calculations for this employee in the period
            calc_result = await self.db.execute(
                select(EmployeeCalculation)
                .join(CalculationRun)
                .where(
                    EmployeeCalculation.employee_id == emp.id,
                    CalculationRun.period_start >= period_start,
                    CalculationRun.period_end <= period_end,
                    CalculationRun.status == "approved",
                )
            )
            calculations = calc_result.scalars().all()

            employee_data.append({
                "employee": emp,
                "calculations": calculations,
            })

        return employee_data

    async def _audit_employee(
        self,
        emp_data: dict,
        period_start: date,
        period_end: date,
    ) -> EmployeeAuditResult:
        """Audit a single employee's calculations."""
        emp = emp_data["employee"]
        calculations = emp_data["calculations"]

        result = EmployeeAuditResult(
            employee_id=emp.id,
            employee_name=f"{emp.first_name} {emp.last_name}",
            ttoc_code=getattr(emp, "ttoc_code", None),
            ttoc_title=getattr(emp, "ttoc_title", None),
        )

        # Aggregate calculation values
        for calc in calculations:
            # The "estimated" values are what was originally calculated
            # without SafeHarbor (simple 1.5x assumption)
            estimated_ot = self._estimate_simple_ot_premium(calc)
            correct_ot = getattr(calc, "qualified_ot_premium", Decimal("0")) or Decimal("0")

            result.estimated_ot_premium += estimated_ot
            result.correct_ot_premium += correct_ot

            # Tip credits
            estimated_tips = self._estimate_simple_tip_credit(calc)
            correct_tips = getattr(calc, "qualified_tip_credit", Decimal("0")) or Decimal("0")

            result.estimated_tip_credit += estimated_tips
            result.correct_tip_credit += correct_tips

            # Phase-out
            phase_out_pct = getattr(calc, "phase_out_percentage", Decimal("0")) or Decimal("0")
            result.phase_out_percentage = max(result.phase_out_percentage, phase_out_pct)

        # Calculate discrepancies
        result.ot_premium_discrepancy = (
            result.correct_ot_premium - result.estimated_ot_premium
        )
        result.tip_credit_discrepancy = (
            result.correct_tip_credit - result.estimated_tip_credit
        )

        result.total_estimated = result.estimated_ot_premium + result.estimated_tip_credit
        result.total_correct = result.correct_ot_premium + result.correct_tip_credit
        result.total_discrepancy = result.total_correct - result.total_estimated

        # Assess risk
        result.risk_level = self._assess_risk(result)
        result.risk_factors = self._identify_risk_factors(result, calculations)
        result.recommendations = self._generate_recommendations(result)

        return result

    def _estimate_simple_ot_premium(self, calc) -> Decimal:
        """
        Estimate OT premium using simple 1.5x method (what employers
        typically calculate without proper FLSA regular rate).
        """
        hourly_rate = getattr(calc, "hourly_rate", None) or Decimal("0")
        ot_hours = getattr(calc, "overtime_hours", None) or Decimal("0")

        # Simple: employer assumes OT premium is just 0.5x base rate
        return hourly_rate * Decimal("0.5") * ot_hours

    def _estimate_simple_tip_credit(self, calc) -> Decimal:
        """
        Estimate tip credit without proper TTOC classification.
        Most employers don't claim this at all, so estimate is 0.
        """
        return Decimal("0")

    def _assess_risk(self, result: EmployeeAuditResult) -> RiskLevel:
        """Determine risk level based on discrepancy magnitude."""
        abs_discrepancy = abs(result.total_discrepancy)

        if abs_discrepancy >= self.DISCREPANCY_THRESHOLD_HIGH:
            return RiskLevel.CRITICAL
        elif abs_discrepancy >= self.DISCREPANCY_THRESHOLD_MEDIUM:
            return RiskLevel.HIGH
        elif abs_discrepancy >= self.DISCREPANCY_THRESHOLD_LOW:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _identify_risk_factors(
        self,
        result: EmployeeAuditResult,
        calculations: list,
    ) -> list[str]:
        """Identify specific risk factors for an employee."""
        factors = []

        if result.ot_premium_discrepancy > Decimal("0"):
            factors.append(
                f"OT premium under-calculated by ${result.ot_premium_discrepancy:.2f} "
                f"(regular rate not properly weighted)"
            )

        if result.ot_premium_discrepancy < Decimal("0"):
            factors.append(
                f"OT premium over-calculated by ${abs(result.ot_premium_discrepancy):.2f}"
            )

        if result.tip_credit_discrepancy > Decimal("0"):
            factors.append(
                f"Unclaimed tip credit of ${result.tip_credit_discrepancy:.2f}"
            )

        if result.phase_out_percentage > Decimal("0"):
            factors.append(
                f"Phase-out reduces credits by {result.phase_out_percentage:.1f}%"
            )

        if not result.ttoc_code:
            factors.append("No TTOC classification - tip eligibility unknown")

        # Check for missing data in calculations
        for calc in calculations:
            trace = getattr(calc, "calculation_trace", {}) or {}
            if trace.get("missing_data"):
                factors.append(f"Missing data: {', '.join(trace['missing_data'])}")
                break

        return factors

    def _generate_recommendations(
        self,
        result: EmployeeAuditResult,
    ) -> list[str]:
        """Generate actionable recommendations for the employee."""
        recs = []

        if result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            recs.append("Priority: Recalculate and amend affected payroll periods")

        if result.ot_premium_discrepancy != Decimal("0"):
            recs.append("Use weighted average regular rate for OT premium calculation")

        if result.tip_credit_discrepancy > Decimal("0"):
            recs.append("Classify occupation with TTOC code to claim tip credit")

        if not result.ttoc_code:
            recs.append("Complete TTOC occupation classification")

        if result.phase_out_percentage > Decimal("50"):
            recs.append("Review MAGI estimate - significant phase-out applies")

        return recs

    def _identify_top_issues(self, report: RetroAuditReport) -> list[dict[str, Any]]:
        """Identify the most impactful issues across all employees."""
        issues = []

        # Check for systematic OT miscalculation
        if abs(report.ot_premium_total_discrepancy) > Decimal("1000"):
            issues.append({
                "type": "systematic_ot_error",
                "severity": "high",
                "title": "Systematic Overtime Premium Miscalculation",
                "description": (
                    f"Total OT premium discrepancy of "
                    f"${report.ot_premium_total_discrepancy:.2f} suggests "
                    f"regular rate is not being calculated per FLSA Section 7."
                ),
                "impact": float(report.ot_premium_total_discrepancy),
                "recommendation": "Implement weighted average regular rate calculation",
            })

        # Check for unclaimed tip credits
        if report.tip_credit_total_discrepancy > Decimal("500"):
            issues.append({
                "type": "unclaimed_tip_credits",
                "severity": "high",
                "title": "Unclaimed OBBB Tip Credits",
                "description": (
                    f"${report.tip_credit_total_discrepancy:.2f} in tip credits "
                    f"not being claimed due to missing TTOC classifications."
                ),
                "impact": float(report.tip_credit_total_discrepancy),
                "recommendation": "Complete TTOC classification for all tipped employees",
            })

        # Check for high-risk employee count
        critical_count = report.risk_distribution.get("critical", 0)
        high_count = report.risk_distribution.get("high", 0)
        if critical_count + high_count > 0:
            issues.append({
                "type": "high_risk_employees",
                "severity": "critical" if critical_count > 0 else "high",
                "title": f"{critical_count + high_count} Employees at High Risk",
                "description": (
                    f"{critical_count} critical and {high_count} high-risk "
                    f"employees require immediate attention."
                ),
                "impact": float(report.total_discrepancy),
                "recommendation": "Review and correct calculations for flagged employees",
            })

        # Sort by impact
        issues.sort(key=lambda x: abs(x.get("impact", 0)), reverse=True)
        return issues[:10]
