"""
Calculation API Routes

Endpoints for managing calculation runs and viewing results.
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    require_permission,
)
from backend.models.calculation_run import CalculationRun, RunStatus
from backend.models.employee import Employee
from backend.models.employee_calculation import EmployeeCalculation
from backend.models.organization import Organization
from backend.schemas.calculation import (
    CalculationApprovalRequest,
    CalculationRunCreate,
    CalculationRunListResponse,
    CalculationRunResponse,
    CalculationRunSummary,
    EmployeeCalculationResponse,
)

router = APIRouter()


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
    response_model=CalculationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create calculation run",
    description="Create a new calculation run for a pay period.",
)
async def create_calculation_run(
    org_id: UUID,
    request: CalculationRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_CREATE)),
) -> CalculationRunResponse:
    """Create a new calculation run."""
    org = await get_organization_or_404(org_id, db)

    # Validate period
    if request.period_end < request.period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Period end must be after period start",
        )

    # Get employee count
    emp_count = await db.execute(
        select(func.count(Employee.id)).where(
            Employee.organization_id == org_id,
            Employee.employment_status == "active",
        )
    )
    total_employees = emp_count.scalar() or 0

    # Find previous run for comparison
    prev_run = await db.execute(
        select(CalculationRun)
        .where(
            CalculationRun.organization_id == org_id,
            CalculationRun.status == RunStatus.FINALIZED.value,
        )
        .order_by(CalculationRun.period_end.desc())
        .limit(1)
    )
    previous = prev_run.scalar_one_or_none()

    # Create calculation run
    run = CalculationRun(
        organization_id=org_id,
        run_type=request.run_type,
        period_start=request.period_start,
        period_end=request.period_end,
        tax_year=request.tax_year,
        total_employees=total_employees,
        previous_run_id=previous.id if previous else None,
        engine_versions={
            "premium_engine": "v1.0.0",
            "occupation_ai": "v1.0.0",
            "phase_out_filter": "v1.0.0",
        },
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    # Trigger async calculation pipeline via Celery
    from workers.tasks.calculation_tasks import run_calculation_batch

    run_calculation_batch.delay(
        str(org_id),
        str(run.id),
        request.period_start.isoformat(),
        request.period_end.isoformat(),
    )

    return CalculationRunResponse.model_validate(run)


@router.get(
    "/",
    response_model=CalculationRunListResponse,
    summary="List calculation runs",
    description="List calculation runs with pagination and filtering.",
)
async def list_calculation_runs(
    org_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    tax_year: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_READ)),
) -> CalculationRunListResponse:
    """List calculation runs."""
    await get_organization_or_404(org_id, db)

    # Build query
    query = select(CalculationRun).where(CalculationRun.organization_id == org_id)

    if status_filter:
        query = query.where(CalculationRun.status == status_filter)
    if tax_year:
        query = query.where(CalculationRun.tax_year == tax_year)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(CalculationRun.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()

    items = []
    for run in runs:
        progress = 0.0
        if run.total_employees > 0:
            progress = (run.processed_employees / run.total_employees) * 100

        items.append(
            CalculationRunSummary(
                id=run.id,
                run_type=run.run_type,
                period_start=run.period_start,
                period_end=run.period_end,
                status=run.status,
                total_employees=run.total_employees,
                processed_employees=run.processed_employees,
                total_combined_credit=run.total_combined_credit,
                created_at=run.created_at,
                progress_percentage=progress,
            )
        )

    return CalculationRunListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{run_id}",
    response_model=CalculationRunResponse,
    summary="Get calculation run",
    description="Get detailed information about a calculation run.",
)
async def get_calculation_run(
    org_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_READ)),
) -> CalculationRunResponse:
    """Get calculation run by ID."""
    result = await db.execute(
        select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation run {run_id} not found",
        )

    return CalculationRunResponse.model_validate(run)


@router.get(
    "/{run_id}/employees",
    summary="Get employee calculations for run",
    description="Get individual employee calculation results.",
)
async def get_run_employees(
    org_id: UUID,
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    has_anomalies: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_READ)),
) -> dict:
    """Get employee calculations for a run."""
    # Verify run exists
    result = await db.execute(
        select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation run {run_id} not found",
        )

    # Build query
    query = select(EmployeeCalculation).where(
        EmployeeCalculation.calculation_run_id == run_id
    )

    if status_filter:
        query = query.where(EmployeeCalculation.status == status_filter)
    if has_anomalies is True:
        query = query.where(EmployeeCalculation.anomaly_flags != [])
    elif has_anomalies is False:
        query = query.where(EmployeeCalculation.anomaly_flags == [])

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    calculations = result.scalars().all()

    return {
        "items": [EmployeeCalculationResponse.model_validate(c) for c in calculations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post(
    "/{run_id}/submit",
    summary="Submit for approval",
    description="Submit a completed calculation run for approval.",
)
async def submit_for_approval(
    org_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_CREATE)),
) -> dict:
    """Submit calculation run for approval."""
    result = await db.execute(
        select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation run {run_id} not found",
        )

    if run.status != RunStatus.CALCULATING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit run in status '{run.status}'",
        )

    run.status = RunStatus.PENDING_APPROVAL.value
    run.submitted_at = datetime.utcnow()
    # run.submitted_by = current_user.id  # TODO: Get from auth

    await db.flush()

    return {
        "run_id": str(run_id),
        "status": run.status,
        "message": "Calculation run submitted for approval",
    }


@router.post(
    "/{run_id}/approve",
    summary="Approve or reject calculation",
    description="Approve or reject a calculation run.",
)
async def approve_calculation(
    org_id: UUID,
    run_id: UUID,
    request: CalculationApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_APPROVE)),
) -> dict:
    """Approve or reject calculation run."""
    result = await db.execute(
        select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation run {run_id} not found",
        )

    if run.status != RunStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve run in status '{run.status}'",
        )

    if request.action == "approve":
        run.status = RunStatus.APPROVED.value
        run.approved_at = datetime.utcnow()
        # run.approved_by = current_user.id  # TODO: Get from auth
        message = "Calculation run approved"
    else:
        if not request.reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required",
            )
        run.status = RunStatus.REJECTED.value
        run.rejection_reason = request.reason
        message = "Calculation run rejected"

    await db.flush()

    return {
        "run_id": str(run_id),
        "status": run.status,
        "message": message,
    }


@router.post(
    "/{run_id}/finalize",
    summary="Finalize calculation",
    description="Finalize an approved calculation and write to vault.",
)
async def finalize_calculation(
    org_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.CALC_FINALIZE)),
) -> dict:
    """Finalize calculation and write to vault."""
    result = await db.execute(
        select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation run {run_id} not found",
        )

    if run.status != RunStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot finalize run in status '{run.status}'",
        )

    run.status = RunStatus.FINALIZED.value
    run.finalized_at = datetime.utcnow()

    await db.flush()

    # Write to compliance vault and verify integrity
    from workers.tasks.compliance_tasks import verify_vault_integrity

    verify_vault_integrity.delay(str(org_id))

    return {
        "run_id": str(run_id),
        "status": run.status,
        "message": "Calculation run finalized and written to compliance vault",
    }
