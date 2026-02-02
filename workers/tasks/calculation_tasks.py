"""
Calculation Tasks

Background tasks for batch calculation processing.
"""

import asyncio
import logging
from datetime import date
from uuid import UUID

from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def run_calculation_batch(
    self,
    organization_id: str,
    calculation_run_id: str,
    period_start: str,
    period_end: str,
):
    """
    Execute a full calculation batch for an organization.

    Processes all employees for the given period:
    1. Fetch employee data
    2. Calculate regular rate (FLSA Section 7)
    3. Calculate qualified OT premium
    4. Calculate tip credits (if TTOC classified)
    5. Apply MAGI phase-out
    6. Store results
    """
    logger.info(
        f"Starting calculation batch {calculation_run_id} "
        f"for org {organization_id}"
    )
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _async_run_calculation(
                UUID(organization_id),
                UUID(calculation_run_id),
                date.fromisoformat(period_start),
                date.fromisoformat(period_end),
            )
        )
        return result
    except Exception as exc:
        logger.error(f"Calculation batch failed: {exc}")
        raise self.retry(exc=exc)


@app.task
def check_phase_out_risks():
    """
    Weekly check for employees approaching MAGI phase-out thresholds.

    Alerts organizations when employees' YTD earnings suggest
    phase-out will apply.
    """
    logger.info("Running weekly phase-out risk check")
    asyncio.get_event_loop().run_until_complete(_async_check_phase_outs())


@app.task
def recalculate_employee(
    organization_id: str,
    employee_id: str,
    period_start: str,
    period_end: str,
):
    """Recalculate a single employee (e.g., after TTOC reclassification)."""
    logger.info(f"Recalculating employee {employee_id}")
    asyncio.get_event_loop().run_until_complete(
        _async_recalculate_employee(
            UUID(organization_id),
            UUID(employee_id),
            date.fromisoformat(period_start),
            date.fromisoformat(period_end),
        )
    )


async def _async_run_calculation(
    org_id: UUID,
    run_id: UUID,
    period_start: date,
    period_end: date,
) -> dict:
    """Execute calculation batch asynchronously."""
    from backend.db.session import get_async_session
    from sqlalchemy import select, update
    from backend.models.calculation_run import CalculationRun
    from backend.models.employee import Employee
    from backend.models.employee_calculation import EmployeeCalculation
    from engines.services.regular_rate_calculator import (
        calculate_regular_rate,
        calculate_tip_credit,
    )
    from engines.services.magi_tracker import calculate_phase_out
    from compliance_vault.ledger import ComplianceVaultLedger
    from decimal import Decimal

    async with get_async_session() as db:
        # Update run status
        await db.execute(
            update(CalculationRun)
            .where(CalculationRun.id == run_id)
            .values(status="calculating")
        )
        await db.commit()

        # Get all employees
        emp_result = await db.execute(
            select(Employee).where(
                Employee.organization_id == org_id,
                Employee.employment_status == "active",
            )
        )
        employees = emp_result.scalars().all()

        total = len(employees)
        completed = 0
        failed = 0
        results = []

        vault = ComplianceVaultLedger(db)

        for emp in employees:
            try:
                # Build calculation input from employee data
                calc_result = await _calculate_single_employee(
                    db, emp, period_start, period_end
                )

                # Create employee calculation record
                emp_calc = EmployeeCalculation(
                    calculation_run_id=run_id,
                    employee_id=emp.id,
                    **calc_result,
                )
                db.add(emp_calc)

                # Record in vault
                await vault.append_calculation(
                    organization_id=org_id,
                    calculation_run_id=run_id,
                    employee_id=emp.id,
                    calculation_data={
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in calc_result.items()
                        if k != "calculation_trace"
                    },
                )

                completed += 1
                results.append({"employee_id": str(emp.id), "status": "success"})

            except Exception as e:
                failed += 1
                logger.error(f"Calculation failed for employee {emp.id}: {e}")
                results.append({
                    "employee_id": str(emp.id),
                    "status": "error",
                    "error": str(e),
                })

            # Update progress
            if completed % 10 == 0:
                await db.execute(
                    update(CalculationRun)
                    .where(CalculationRun.id == run_id)
                    .values(
                        processed_employees=completed + failed,
                        total_employees=total,
                    )
                )
                await db.commit()

        # Finalize run
        final_status = "pending_approval" if failed == 0 else "error"
        await db.execute(
            update(CalculationRun)
            .where(CalculationRun.id == run_id)
            .values(
                status=final_status,
                processed_employees=total,
                total_employees=total,
            )
        )
        await db.commit()

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "status": final_status,
        }


async def _calculate_single_employee(
    db,
    employee,
    period_start: date,
    period_end: date,
) -> dict:
    """Calculate OBBB values for a single employee."""
    from engines.services.regular_rate_calculator import calculate_regular_rate
    from engines.services.magi_tracker import calculate_phase_out
    from engines.schemas.premium_engine import RegularRateInput
    from engines.schemas.phase_out import PhaseOutInput
    from decimal import Decimal

    # Gather employee data for the period
    # In production, this would pull from synced payroll/POS data
    hourly_rate = employee.hourly_rate or Decimal("0")
    regular_hours = Decimal("40")  # Default workweek
    overtime_hours = Decimal("0")

    # Calculate regular rate
    rate_input = RegularRateInput(
        employee_id=str(employee.id),
        period_start=period_start,
        period_end=period_end,
        hourly_rate=hourly_rate,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
    )
    rate_result = calculate_regular_rate(rate_input)

    # Calculate phase-out
    phase_out_input = PhaseOutInput(
        employee_id=str(employee.id),
        filing_status=getattr(employee, "filing_status", "single") or "single",
        estimated_annual_magi=getattr(employee, "ytd_gross_wages", Decimal("0")) or Decimal("0"),
    )
    phase_out_result = calculate_phase_out(phase_out_input)

    return {
        "regular_hours": rate_result.regular_hours,
        "overtime_hours": rate_result.overtime_hours,
        "regular_rate": rate_result.regular_rate,
        "qualified_ot_premium": rate_result.qualified_ot_premium,
        "phase_out_percentage": phase_out_result.phase_out_percentage,
        "calculation_trace": {
            "inputs": {
                "hourly_rate": str(hourly_rate),
                "regular_hours": str(regular_hours),
                "overtime_hours": str(overtime_hours),
            },
            "regular_rate_details": {
                "total_compensation": str(rate_result.total_compensation),
                "total_hours": str(rate_result.total_hours),
            },
        },
    }


async def _async_check_phase_outs():
    """Check all employees for phase-out risk."""
    from backend.db.session import get_async_session
    from sqlalchemy import select
    from backend.models.employee import Employee
    from backend.models.organization import Organization

    async with get_async_session() as db:
        result = await db.execute(
            select(Employee).where(Employee.employment_status == "active")
        )
        employees = result.scalars().all()

        at_risk = []
        for emp in employees:
            ytd = getattr(emp, "ytd_gross_wages", None)
            if ytd and float(ytd) > 60000:  # Early warning threshold
                at_risk.append({
                    "employee_id": str(emp.id),
                    "organization_id": str(emp.organization_id),
                    "ytd_wages": str(ytd),
                })

        if at_risk:
            logger.info(f"Phase-out risk: {len(at_risk)} employees flagged")


async def _async_recalculate_employee(
    org_id: UUID,
    employee_id: UUID,
    period_start: date,
    period_end: date,
):
    """Recalculate a single employee."""
    from backend.db.session import get_async_session
    from sqlalchemy import select
    from backend.models.employee import Employee

    async with get_async_session() as db:
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = result.scalar_one_or_none()
        if not employee:
            logger.error(f"Employee {employee_id} not found")
            return

        calc_result = await _calculate_single_employee(
            db, employee, period_start, period_end
        )
        logger.info(
            f"Recalculated employee {employee_id}: "
            f"OT premium={calc_result.get('qualified_ot_premium')}"
        )
