"""
Compliance API Routes

Handles retro-audit reports, compliance vault, and audit defense packs.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    require_permission,
)
from backend.services.retro_audit import RetroAuditReport, RetroAuditService

router = APIRouter()


class RetroAuditRequest(BaseModel):
    """Request to generate a retro-audit report."""
    tax_year: int = 2025
    period_start: date | None = None
    period_end: date | None = None


class AuditPackRequest(BaseModel):
    """Request to generate an audit defense pack."""
    tax_year: int = 2025
    include_calculations: bool = True
    include_source_data: bool = True
    include_classifications: bool = True
    include_vault_entries: bool = True
    employee_ids: list[UUID] | None = None


class VaultEntryResponse(BaseModel):
    """Response for a compliance vault entry."""
    id: UUID
    entry_type: str
    entry_hash: str
    previous_hash: str | None
    sequence_number: int
    created_at: str
    actor_id: str | None
    summary: str | None


class VaultIntegrityResponse(BaseModel):
    """Response for vault integrity check."""
    is_valid: bool
    total_entries: int
    entries_checked: int
    first_broken_entry: int | None = None
    message: str


@router.post(
    "/organizations/{org_id}/retro-audit",
    response_model=RetroAuditReport,
)
async def generate_retro_audit(
    org_id: UUID,
    request: RetroAuditRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.COMPLIANCE_READ)),
):
    """
    Generate a retro-audit report for an organization.

    Compares estimated vs. correct OBBB tax exemption values
    and identifies discrepancies with risk assessments.
    """
    service = RetroAuditService(db)
    report = await service.generate_report(
        organization_id=org_id,
        tax_year=request.tax_year,
        period_start=request.period_start,
        period_end=request.period_end,
    )
    return report


@router.get(
    "/organizations/{org_id}/vault",
    response_model=list[VaultEntryResponse],
)
async def list_vault_entries(
    org_id: UUID,
    entry_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.VAULT_READ)),
):
    """List compliance vault entries for an organization."""
    from sqlalchemy import select, desc
    from backend.models.compliance_vault import ComplianceVault

    query = select(ComplianceVault).where(
        ComplianceVault.organization_id == org_id
    )

    if entry_type:
        query = query.where(ComplianceVault.entry_type == entry_type)

    query = query.order_by(desc(ComplianceVault.sequence_number))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        VaultEntryResponse(
            id=entry.id,
            entry_type=entry.entry_type,
            entry_hash=entry.entry_hash,
            previous_hash=entry.previous_hash,
            sequence_number=entry.sequence_number,
            created_at=entry.created_at.isoformat(),
            actor_id=str(entry.actor_id) if entry.actor_id else None,
            summary=_extract_summary(entry.content),
        )
        for entry in entries
    ]


@router.get(
    "/organizations/{org_id}/vault/integrity",
    response_model=VaultIntegrityResponse,
)
async def verify_vault_integrity(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.VAULT_READ)),
):
    """
    Verify the integrity of the compliance vault hash chain.

    Checks that all entries form a valid chain with correct hashes.
    """
    from compliance_vault.integrity import verify_chain

    result = await verify_chain(db, org_id)
    return VaultIntegrityResponse(**result)


@router.post(
    "/organizations/{org_id}/audit-pack",
)
async def generate_audit_pack(
    org_id: UUID,
    request: AuditPackRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.COMPLIANCE_EXPORT)),
):
    """
    Generate an Audit Defense Pack for IRS examination.

    Returns a comprehensive package of all supporting documentation
    for OBBB tax credit claims.
    """
    from compliance_vault.export import generate_audit_pack

    pack = await generate_audit_pack(
        db=db,
        organization_id=org_id,
        tax_year=request.tax_year,
        include_calculations=request.include_calculations,
        include_source_data=request.include_source_data,
        include_classifications=request.include_classifications,
        include_vault_entries=request.include_vault_entries,
        employee_ids=request.employee_ids,
    )
    return pack


@router.get(
    "/organizations/{org_id}/audit-pack/pdf",
    summary="Download audit pack as PDF",
)
async def download_audit_pack_pdf(
    org_id: UUID,
    tax_year: int = Query(default=2025),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.COMPLIANCE_EXPORT)),
):
    """Generate and download a PDF audit defense pack."""
    import io

    from fastapi.responses import StreamingResponse
    from sqlalchemy import select

    from backend.models.calculation_run import CalculationRun
    from backend.models.compliance_vault import ComplianceVault
    from backend.models.employee import Employee
    from backend.models.organization import Organization
    from backend.models.ttoc_classification import TTOCClassification
    from compliance_vault.pdf_generator import generate_audit_pack_pdf

    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Calculation runs
    calc_result = await db.execute(
        select(CalculationRun)
        .where(CalculationRun.organization_id == org_id, CalculationRun.tax_year == tax_year)
        .order_by(CalculationRun.period_start)
    )
    calculations = [
        {
            "id": str(r.id), "period_start": str(r.period_start),
            "period_end": str(r.period_end), "status": r.status,
            "total_employees": r.total_employees,
            "total_qualified_ot": float(r.total_qualified_ot_premium or 0),
            "total_qualified_tips": float(r.total_qualified_tips or 0),
            "total_combined_credit": float(r.total_combined_credit or 0),
        }
        for r in calc_result.scalars().all()
    ]

    # Employees
    emp_result = await db.execute(
        select(Employee).where(Employee.organization_id == org_id).order_by(Employee.last_name)
    )
    employees = [
        {
            "first_name": e.first_name, "last_name": e.last_name,
            "job_title": e.job_title, "ttoc_code": e.ttoc_code,
            "filing_status": e.filing_status, "hourly_rate": float(e.hourly_rate or 0),
        }
        for e in emp_result.scalars().all()
    ]

    # Vault entries
    vault_result = await db.execute(
        select(ComplianceVault).where(ComplianceVault.organization_id == org_id)
        .order_by(ComplianceVault.sequence_number).limit(100)
    )
    vault_entries = [
        {
            "sequence_number": v.sequence_number, "entry_type": v.entry_type,
            "entry_hash": v.entry_hash, "created_at": v.created_at.isoformat(),
        }
        for v in vault_result.scalars().all()
    ]

    # TTOC classifications
    cls_result = await db.execute(
        select(TTOCClassification).where(TTOCClassification.organization_id == org_id)
        .order_by(TTOCClassification.created_at.desc()).limit(100)
    )
    classifications = [
        {
            "employee_name": str(c.employee_id)[:8], "ttoc_code": c.ttoc_code,
            "ttoc_description": c.ttoc_description or "",
            "confidence": float(c.confidence_score or 0),
            "method": c.classification_method or "",
        }
        for c in cls_result.scalars().all()
    ]

    pdf_bytes = generate_audit_pack_pdf(
        org_name=org.name, ein=org.ein, tax_year=tax_year,
        calculations=calculations, employees=employees,
        vault_entries=vault_entries, classifications=classifications,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=safeharbor_audit_pack_{org.ein}_{tax_year}.pdf"
            )
        },
    )


def _extract_summary(content: dict | None) -> str | None:
    """Extract a human-readable summary from vault entry content."""
    if not content:
        return None
    if "summary" in content:
        return content["summary"]
    if "action" in content:
        return f"{content['action']}: {content.get('details', '')}"
    return None
