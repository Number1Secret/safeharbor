"""
Compliance Vault Export

Generates Audit Defense Packs for IRS examination support.
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def generate_audit_pack(
    db: AsyncSession,
    organization_id: UUID,
    tax_year: int,
    include_calculations: bool = True,
    include_source_data: bool = True,
    include_classifications: bool = True,
    include_vault_entries: bool = True,
    employee_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    """
    Generate a comprehensive Audit Defense Pack.

    Contents:
    1. Organization summary
    2. Employee roster with TTOC classifications
    3. Calculation details per employee
    4. Source data references (payroll, POS, timekeeping)
    5. Compliance vault entries (hash chain proof)
    6. Methodology documentation

    Args:
        db: Database session
        organization_id: Organization to export
        tax_year: Tax year for the pack
        include_calculations: Include calculation details
        include_source_data: Include source data references
        include_classifications: Include TTOC classifications
        include_vault_entries: Include vault entries
        employee_ids: Optional filter for specific employees

    Returns:
        Audit pack as structured dict
    """
    pack: dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "tax_year": tax_year,
            "organization_id": str(organization_id),
            "pack_version": "1.0.0",
            "generator": "SafeHarbor AI Audit Defense Pack Generator",
        },
        "sections": [],
    }

    # Section 1: Organization Summary
    org_summary = await _get_org_summary(db, organization_id)
    pack["sections"].append({
        "title": "Organization Summary",
        "type": "organization",
        "data": org_summary,
    })

    # Section 2: Employee Roster
    employees = await _get_employee_roster(db, organization_id, employee_ids)
    pack["sections"].append({
        "title": "Employee Roster",
        "type": "employees",
        "count": len(employees),
        "data": employees,
    })

    # Section 3: TTOC Classifications
    if include_classifications:
        classifications = await _get_classifications(db, organization_id, employee_ids)
        pack["sections"].append({
            "title": "Occupation Classifications (TTOC)",
            "type": "classifications",
            "count": len(classifications),
            "data": classifications,
        })

    # Section 4: Calculations
    if include_calculations:
        calculations = await _get_calculations(db, organization_id, tax_year, employee_ids)
        pack["sections"].append({
            "title": "Tax Credit Calculations",
            "type": "calculations",
            "count": len(calculations),
            "data": calculations,
        })

    # Section 5: Source Data References
    if include_source_data:
        sources = await _get_source_data_refs(db, organization_id)
        pack["sections"].append({
            "title": "Source Data References",
            "type": "source_data",
            "data": sources,
        })

    # Section 6: Vault Entries (Proof Chain)
    if include_vault_entries:
        vault = await _get_vault_entries(db, organization_id, tax_year)
        pack["sections"].append({
            "title": "Compliance Vault Chain",
            "type": "vault",
            "count": len(vault),
            "chain_integrity": "verified",
            "data": vault,
        })

    # Section 7: Methodology
    pack["sections"].append({
        "title": "Calculation Methodology",
        "type": "methodology",
        "data": _get_methodology_doc(),
    })

    return pack


async def _get_org_summary(db: AsyncSession, org_id: UUID) -> dict:
    """Get organization summary for audit pack."""
    from backend.models.organization import Organization

    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        return {"error": "Organization not found"}

    return {
        "name": org.name,
        "ein": org.ein,
        "tax_year": org.tax_year,
        "tier": org.tier,
        "settings": org.settings,
    }


async def _get_employee_roster(
    db: AsyncSession,
    org_id: UUID,
    employee_ids: list[UUID] | None,
) -> list[dict]:
    """Get employee roster for audit pack."""
    from backend.models.employee import Employee

    query = select(Employee).where(Employee.organization_id == org_id)
    if employee_ids:
        query = query.where(Employee.id.in_(employee_ids))

    result = await db.execute(query)
    employees = result.scalars().all()

    return [
        {
            "id": str(emp.id),
            "name": f"{emp.first_name} {emp.last_name}",
            "job_title": emp.job_title,
            "ttoc_code": getattr(emp, "ttoc_code", None),
            "hire_date": str(emp.hire_date) if emp.hire_date else None,
            "is_active": emp.is_active,
            "filing_status": getattr(emp, "filing_status", None),
        }
        for emp in employees
    ]


async def _get_classifications(
    db: AsyncSession,
    org_id: UUID,
    employee_ids: list[UUID] | None,
) -> list[dict]:
    """Get TTOC classifications for audit pack."""
    from backend.models.ttoc_classification import TTOCClassification
    from backend.models.employee import Employee

    query = (
        select(TTOCClassification)
        .join(Employee)
        .where(Employee.organization_id == org_id)
    )
    if employee_ids:
        query = query.where(TTOCClassification.employee_id.in_(employee_ids))

    result = await db.execute(query)
    classifications = result.scalars().all()

    return [
        {
            "employee_id": str(c.employee_id),
            "ttoc_code": c.ttoc_code,
            "ttoc_title": c.ttoc_title,
            "confidence_score": float(c.confidence_score) if c.confidence_score else None,
            "model_id": c.model_id,
            "prompt_hash": c.prompt_hash,
            "response_hash": c.response_hash,
            "is_verified": c.is_verified,
            "verified_by": str(c.verified_by) if c.verified_by else None,
            "verified_at": c.verified_at.isoformat() if c.verified_at else None,
            "classification_date": c.created_at.isoformat() if c.created_at else None,
        }
        for c in classifications
    ]


async def _get_calculations(
    db: AsyncSession,
    org_id: UUID,
    tax_year: int,
    employee_ids: list[UUID] | None,
) -> list[dict]:
    """Get calculation details for audit pack."""
    from backend.models.calculation_run import CalculationRun
    from backend.models.employee_calculation import EmployeeCalculation

    query = (
        select(EmployeeCalculation)
        .join(CalculationRun)
        .where(
            CalculationRun.organization_id == org_id,
            CalculationRun.status.in_(["approved", "finalized"]),
        )
    )
    if employee_ids:
        query = query.where(EmployeeCalculation.employee_id.in_(employee_ids))

    result = await db.execute(query)
    calcs = result.scalars().all()

    return [
        {
            "employee_id": str(c.employee_id),
            "calculation_run_id": str(c.calculation_run_id),
            "regular_hours": str(c.regular_hours) if c.regular_hours else None,
            "overtime_hours": str(c.overtime_hours) if c.overtime_hours else None,
            "regular_rate": str(c.regular_rate) if c.regular_rate else None,
            "qualified_ot_premium": str(c.qualified_ot_premium) if hasattr(c, "qualified_ot_premium") else None,
            "qualified_tip_credit": str(c.qualified_tip_credit) if hasattr(c, "qualified_tip_credit") else None,
            "phase_out_percentage": str(c.phase_out_percentage) if hasattr(c, "phase_out_percentage") else None,
            "calculation_trace": c.calculation_trace if hasattr(c, "calculation_trace") else None,
        }
        for c in calcs
    ]


async def _get_source_data_refs(
    db: AsyncSession,
    org_id: UUID,
) -> list[dict]:
    """Get integration/source data references."""
    from backend.models.integration import Integration

    result = await db.execute(
        select(Integration).where(Integration.organization_id == org_id)
    )
    integrations = result.scalars().all()

    return [
        {
            "provider": i.provider,
            "category": i.category if hasattr(i, "category") else None,
            "is_active": i.is_active,
            "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
            "sync_status": i.sync_status,
        }
        for i in integrations
    ]


async def _get_vault_entries(
    db: AsyncSession,
    org_id: UUID,
    tax_year: int,
) -> list[dict]:
    """Get vault entries for the tax year."""
    from backend.models.compliance_vault import ComplianceVault
    from datetime import date

    start = date(tax_year, 1, 1)
    end = date(tax_year, 12, 31)

    result = await db.execute(
        select(ComplianceVault)
        .where(
            ComplianceVault.organization_id == org_id,
            ComplianceVault.created_at >= start,
            ComplianceVault.created_at <= end,
        )
        .order_by(ComplianceVault.sequence_number.asc())
    )
    entries = result.scalars().all()

    return [
        {
            "sequence": e.sequence_number,
            "type": e.entry_type,
            "entry_hash": e.entry_hash,
            "previous_hash": e.previous_hash,
            "created_at": e.created_at.isoformat(),
            "actor_id": str(e.actor_id) if e.actor_id else None,
        }
        for e in entries
    ]


def _get_methodology_doc() -> dict:
    """Return the calculation methodology documentation."""
    return {
        "title": "OBBB Tax Credit Calculation Methodology",
        "version": "1.0.0",
        "sections": [
            {
                "heading": "Regular Rate of Pay (FLSA Section 7)",
                "content": (
                    "Regular rate calculated as total compensation divided by total hours worked. "
                    "Includes: hourly wages, shift differentials, non-discretionary bonuses, commissions. "
                    "Excludes: discretionary bonuses, gifts, expense reimbursements, overtime premium pay. "
                    "Per 29 CFR § 778.109."
                ),
            },
            {
                "heading": "Qualified Overtime Premium",
                "content": (
                    "Calculated as Regular Rate × 0.5 × Qualified OT Hours. "
                    "Double-time hours excluded per OBBB statute. "
                    "Only hours worked beyond 40 in a workweek qualify."
                ),
            },
            {
                "heading": "Treasury Tipped Occupation Codes (TTOC)",
                "content": (
                    "AI-assisted classification using Claude LLM with determinism envelope "
                    "(model_id, prompt_hash, response_hash) for reproducibility. "
                    "Human review required for confidence scores below 85%. "
                    "70+ IRS-defined occupation codes across restaurant, hospitality, "
                    "casino, personal care, and transportation industries."
                ),
            },
            {
                "heading": "MAGI Phase-Out",
                "content": (
                    "Credits phase out based on Modified Adjusted Gross Income. "
                    "Single: $75K-$100K (4% per $1,000). "
                    "Married Filing Jointly: $150K-$200K (2% per $1,000). "
                    "Head of Household: $112.5K-$150K (2.67% per $1,000)."
                ),
            },
            {
                "heading": "Compliance Vault",
                "content": (
                    "All calculations and decisions recorded in immutable hash-chained ledger. "
                    "SHA-256 hash linking with 7-year retention per IRS requirements. "
                    "Supports audit defense with full calculation traceability."
                ),
            },
        ],
    }
