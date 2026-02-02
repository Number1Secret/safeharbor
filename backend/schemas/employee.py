"""
Employee Pydantic Schemas

API request/response models for Employee endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmployeeBase(BaseModel):
    """Base employee fields shared across schemas."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    hire_date: date


class EmployeeCreate(EmployeeBase):
    """Schema for creating a new employee."""

    ssn: str = Field(
        ...,
        pattern=r"^\d{3}-\d{2}-\d{4}$",
        description="Social Security Number (XXX-XX-XXXX format) - will be hashed",
    )
    job_title: str | None = Field(default=None, max_length=255)
    job_description: str | None = None
    department: str | None = Field(default=None, max_length=100)
    duties: list[str] = Field(default_factory=list)
    hourly_rate: float | None = Field(default=None, ge=0)
    is_hourly: bool = True
    filing_status: Literal[
        "single", "married_joint", "married_separate", "head_of_household"
    ] | None = None
    estimated_annual_magi: float | None = Field(default=None, ge=0)
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description="External system IDs (e.g., {'adp': '123', 'toast': '456'})",
    )


class EmployeeUpdate(BaseModel):
    """Schema for updating an employee."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    job_title: str | None = Field(default=None, max_length=255)
    job_description: str | None = None
    department: str | None = Field(default=None, max_length=100)
    duties: list[str] | None = None
    hourly_rate: float | None = Field(default=None, ge=0)
    is_hourly: bool | None = None
    employment_status: Literal["active", "terminated", "leave"] | None = None
    termination_date: date | None = None
    filing_status: Literal[
        "single", "married_joint", "married_separate", "head_of_household"
    ] | None = None
    estimated_annual_magi: float | None = Field(default=None, ge=0)
    external_ids: dict[str, str] | None = None


class TTOCInfo(BaseModel):
    """TTOC classification information."""

    model_config = ConfigDict(from_attributes=True)

    ttoc_code: str | None
    ttoc_description: str | None = None
    confidence_score: float | None
    is_tipped_occupation: bool
    is_verified: bool
    verified_at: datetime | None = None


class EmployeeResponse(EmployeeBase):
    """Schema for employee response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    employment_status: str
    termination_date: date | None
    job_title: str | None
    department: str | None
    hourly_rate: float | None
    is_hourly: bool
    filing_status: str | None
    estimated_annual_magi: float | None

    # TTOC Classification
    ttoc_code: str | None
    ttoc_verified: bool
    ttoc_verified_at: datetime | None

    # Year-to-date totals
    ytd_gross_wages: float
    ytd_overtime_hours: float
    ytd_tips: float
    ytd_qualified_ot_premium: float
    ytd_qualified_tips: float

    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    """Schema for paginated employee list."""

    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EmployeeCalculationSummary(BaseModel):
    """Summary of an employee's calculation for a period."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: UUID
    employee_name: str
    calculation_run_id: UUID
    period_start: date
    period_end: date

    # Key metrics
    total_hours: Decimal | None
    overtime_hours: Decimal | None
    regular_rate: Decimal | None
    qualified_ot_premium: Decimal | None
    qualified_tips: Decimal | None
    combined_credit_final: Decimal | None

    # Status
    status: str
    has_anomalies: bool
    anomaly_flags: list[str]
