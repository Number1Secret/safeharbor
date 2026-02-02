"""
Employee API Routes

Endpoints for managing employees within an organization.
"""

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    require_permission,
)
from backend.models.employee import Employee
from backend.models.organization import Organization
from backend.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)

router = APIRouter()


def hash_ssn(ssn: str) -> str:
    """Hash SSN for storage. Never store raw SSN."""
    # Remove formatting
    clean_ssn = ssn.replace("-", "").replace(" ", "")
    return hashlib.sha256(clean_ssn.encode()).hexdigest()


async def get_organization_or_404(org_id: UUID, db: AsyncSession) -> Organization:
    """Helper to get organization or raise 404."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )
    return org


@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee",
    description="Create a new employee record for tax tracking.",
)
async def create_employee(
    org_id: UUID,
    request: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.EMPLOYEE_WRITE)),
) -> EmployeeResponse:
    """Create a new employee."""
    await get_organization_or_404(org_id, db)

    # Hash SSN
    ssn_hash = hash_ssn(request.ssn)

    # Check for duplicate
    existing = await db.execute(
        select(Employee).where(
            Employee.organization_id == org_id,
            Employee.ssn_hash == ssn_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee with this SSN already exists in organization",
        )

    employee = Employee(
        organization_id=org_id,
        first_name=request.first_name,
        last_name=request.last_name,
        ssn_hash=ssn_hash,
        hire_date=request.hire_date,
        job_title=request.job_title,
        job_description=request.job_description,
        department=request.department,
        duties=request.duties,
        hourly_rate=request.hourly_rate,
        is_hourly=request.is_hourly,
        filing_status=request.filing_status,
        estimated_annual_magi=request.estimated_annual_magi,
        external_ids=request.external_ids,
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)

    return EmployeeResponse.model_validate(employee)


@router.get(
    "/",
    response_model=EmployeeListResponse,
    summary="List employees",
    description="List employees with pagination and filtering.",
)
async def list_employees(
    org_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    department: str | None = None,
    has_ttoc: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.EMPLOYEE_READ)),
) -> EmployeeListResponse:
    """List employees with filtering."""
    await get_organization_or_404(org_id, db)

    # Build query
    query = select(Employee).where(Employee.organization_id == org_id)

    if status_filter:
        query = query.where(Employee.employment_status == status_filter)
    if department:
        query = query.where(Employee.department == department)
    if has_ttoc is not None:
        if has_ttoc:
            query = query.where(Employee.ttoc_code.isnot(None))
        else:
            query = query.where(Employee.ttoc_code.is_(None))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Employee.last_name, Employee.first_name)
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    employees = result.scalars().all()

    return EmployeeListResponse(
        items=[EmployeeResponse.model_validate(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get employee",
    description="Get detailed employee information.",
)
async def get_employee(
    org_id: UUID,
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.EMPLOYEE_READ)),
) -> EmployeeResponse:
    """Get employee by ID."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == org_id,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )

    return EmployeeResponse.model_validate(employee)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update employee",
    description="Update employee information.",
)
async def update_employee(
    org_id: UUID,
    employee_id: UUID,
    request: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.EMPLOYEE_WRITE)),
) -> EmployeeResponse:
    """Update employee."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == org_id,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)

    await db.flush()
    await db.refresh(employee)

    return EmployeeResponse.model_validate(employee)


@router.post(
    "/{employee_id}/classify",
    summary="Trigger TTOC classification",
    description="Request AI classification of employee's occupation code.",
)
async def classify_employee_ttoc(
    org_id: UUID,
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.EMPLOYEE_WRITE)),
) -> dict:
    """Trigger TTOC classification for employee."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == org_id,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )

    if not employee.job_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee must have a job title for classification",
        )

    # Trigger async recalculation which includes TTOC classification
    from workers.tasks.calculation_tasks import recalculate_employee

    recalculate_employee.delay(
        str(org_id),
        str(employee_id),
        "",  # period_start - empty signals classification-only
        "",  # period_end
    )

    return {
        "employee_id": str(employee_id),
        "status": "queued",
        "message": "TTOC classification has been queued",
        "job_title": employee.job_title,
    }


@router.get(
    "/{employee_id}/calculations",
    summary="Get employee calculation history",
    description="Get calculation history for a specific employee.",
)
async def get_employee_calculations(
    org_id: UUID,
    employee_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_READ)),
) -> list[dict]:
    """Get calculation history for employee."""
    # Verify employee exists
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == org_id,
        )
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )

    # TODO: Query EmployeeCalculation table
    # For now, return YTD summary
    return [
        {
            "employee_id": str(employee_id),
            "type": "ytd_summary",
            "ytd_gross_wages": employee.ytd_gross_wages,
            "ytd_overtime_hours": employee.ytd_overtime_hours,
            "ytd_tips": employee.ytd_tips,
            "ytd_qualified_ot_premium": employee.ytd_qualified_ot_premium,
            "ytd_qualified_tips": employee.ytd_qualified_tips,
        }
    ]
