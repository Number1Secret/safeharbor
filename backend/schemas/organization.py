"""
Organization Pydantic Schemas

API request/response models for Organization endpoints.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationBase(BaseModel):
    """Base organization fields shared across schemas."""

    name: str = Field(..., min_length=1, max_length=255, description="Legal business name")
    ein: str = Field(
        ...,
        pattern=r"^\d{2}-\d{7}$",
        description="Employer Identification Number (XX-XXXXXXX format)",
    )
    tax_year: int = Field(default=2025, ge=2024, le=2030, description="Tax year for calculations")


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""

    tier: Literal["starter", "pro", "enterprise"] = Field(
        default="starter",
        description="Subscription tier",
    )
    tip_credit_enabled: bool = Field(
        default=False,
        description="Enable tip credit calculations",
    )
    overtime_credit_enabled: bool = Field(
        default=False,
        description="Enable overtime credit calculations",
    )
    workweek_start: Literal[
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ] = Field(
        default="sunday",
        description="FLSA workweek start day",
    )
    primary_contact_email: str | None = Field(
        default=None,
        max_length=255,
        description="Primary contact email",
    )
    primary_contact_name: str | None = Field(
        default=None,
        max_length=255,
        description="Primary contact name",
    )
    settings: dict = Field(
        default_factory=dict,
        description="Organization-specific configuration",
    )

    @field_validator("ein")
    @classmethod
    def validate_ein_format(cls, v: str) -> str:
        """Validate EIN format and clean input."""
        # Remove any extra whitespace
        v = v.strip()
        # Verify format
        if not v or len(v) != 10:
            raise ValueError("EIN must be in XX-XXXXXXX format")
        return v


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    tax_year: int | None = Field(default=None, ge=2024, le=2030)
    tier: Literal["starter", "pro", "enterprise"] | None = None
    tip_credit_enabled: bool | None = None
    overtime_credit_enabled: bool | None = None
    penalty_guarantee_active: bool | None = None
    workweek_start: Literal[
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ] | None = None
    status: Literal["active", "suspended", "closed"] | None = None
    primary_contact_email: str | None = Field(default=None, max_length=255)
    primary_contact_name: str | None = Field(default=None, max_length=255)
    settings: dict | None = None


class OrganizationResponse(OrganizationBase):
    """Schema for organization response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tier: str
    tip_credit_enabled: bool
    overtime_credit_enabled: bool
    penalty_guarantee_active: bool
    status: str
    workweek_start: str
    primary_contact_email: str | None
    primary_contact_name: str | None
    settings: dict
    onboarded_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Computed fields for dashboard
    employee_count: int = Field(default=0, description="Total number of employees")
    connected_integrations: int = Field(default=0, description="Number of connected integrations")


class OrganizationSummary(BaseModel):
    """Summary schema for organization listing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    ein: str
    tier: str
    status: str
    employee_count: int = 0
    created_at: datetime
