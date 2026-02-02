"""
Organization API Routes

Endpoints for managing organizations (multi-tenant employers).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    require_org_access,
    require_permission,
)
from backend.models.employee import Employee
from backend.models.integration import Integration
from backend.models.organization import Organization
from backend.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationSummary,
    OrganizationUpdate,
)

router = APIRouter()


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    description="Create a new organization (employer) for tax compliance tracking.",
)
async def create_organization(
    request: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.ORG_WRITE)),
) -> OrganizationResponse:
    """Create a new organization."""
    # Check for duplicate EIN
    existing = await db.execute(
        select(Organization).where(Organization.ein == request.ein)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with EIN {request.ein} already exists",
        )

    org = Organization(
        name=request.name,
        ein=request.ein,
        tax_year=request.tax_year,
        tier=request.tier,
        tip_credit_enabled=request.tip_credit_enabled,
        overtime_credit_enabled=request.overtime_credit_enabled,
        workweek_start=request.workweek_start,
        primary_contact_email=request.primary_contact_email,
        primary_contact_name=request.primary_contact_name,
        settings=request.settings,
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)

    return OrganizationResponse(
        **org.__dict__,
        employee_count=0,
        connected_integrations=0,
    )


@router.get(
    "/",
    response_model=list[OrganizationSummary],
    summary="List organizations",
    description="List all organizations with summary information.",
)
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.ORG_READ)),
) -> list[OrganizationSummary]:
    """List all organizations."""
    result = await db.execute(
        select(Organization)
        .order_by(Organization.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    orgs = result.scalars().all()

    summaries = []
    for org in orgs:
        # Get employee count
        emp_count = await db.execute(
            select(func.count(Employee.id)).where(Employee.organization_id == org.id)
        )
        count = emp_count.scalar() or 0

        summaries.append(
            OrganizationSummary(
                id=org.id,
                name=org.name,
                ein=org.ein,
                tier=org.tier,
                status=org.status,
                employee_count=count,
                created_at=org.created_at,
            )
        )

    return summaries


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization",
    description="Get detailed information about an organization.",
)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.ORG_READ)),
) -> OrganizationResponse:
    """Get organization by ID."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    # Get counts
    emp_count = await db.execute(
        select(func.count(Employee.id)).where(Employee.organization_id == org_id)
    )
    int_count = await db.execute(
        select(func.count(Integration.id)).where(
            Integration.organization_id == org_id,
            Integration.status == "connected",
        )
    )

    return OrganizationResponse(
        **org.__dict__,
        employee_count=emp_count.scalar() or 0,
        connected_integrations=int_count.scalar() or 0,
    )


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    description="Update organization settings and configuration.",
)
async def update_organization(
    org_id: UUID,
    request: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.ORG_WRITE)),
) -> OrganizationResponse:
    """Update organization."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    await db.flush()
    await db.refresh(org)

    # Get counts
    emp_count = await db.execute(
        select(func.count(Employee.id)).where(Employee.organization_id == org_id)
    )
    int_count = await db.execute(
        select(func.count(Integration.id)).where(
            Integration.organization_id == org_id,
            Integration.status == "connected",
        )
    )

    return OrganizationResponse(
        **org.__dict__,
        employee_count=emp_count.scalar() or 0,
        connected_integrations=int_count.scalar() or 0,
    )


@router.get(
    "/{org_id}/summary",
    summary="Get organization dashboard summary",
    description="Get aggregated metrics for the organization dashboard.",
)
async def get_organization_summary(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.ORG_READ)),
) -> dict:
    """Get dashboard summary for organization."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    # Get employee counts
    total_employees = await db.execute(
        select(func.count(Employee.id)).where(
            Employee.organization_id == org_id,
            Employee.employment_status == "active",
        )
    )

    # Get YTD totals
    ytd_ot_premium = await db.execute(
        select(func.sum(Employee.ytd_qualified_ot_premium)).where(
            Employee.organization_id == org_id
        )
    )
    ytd_tips = await db.execute(
        select(func.sum(Employee.ytd_qualified_tips)).where(
            Employee.organization_id == org_id
        )
    )

    active_count = total_employees.scalar() or 0
    ot_premium_total = float(ytd_ot_premium.scalar() or 0)
    tips_total = float(ytd_tips.scalar() or 0)

    return {
        "organization_id": str(org_id),
        "organization_name": org.name,
        "tax_year": org.tax_year,
        "active_employees": active_count,
        "ytd_qualified_ot_premium": ot_premium_total,
        "ytd_qualified_tips": tips_total,
        "ytd_total_credits": ot_premium_total + tips_total,
        "penalty_guarantee_active": org.penalty_guarantee_active,
        "tip_credit_enabled": org.tip_credit_enabled,
        "overtime_credit_enabled": org.overtime_credit_enabled,
    }
