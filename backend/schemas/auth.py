"""
Auth Pydantic Schemas

Request/response models for authentication endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Schema for new user + organization registration."""

    # Organization details
    org_name: str = Field(..., min_length=1, max_length=255, description="Legal business name")
    ein: str = Field(
        ...,
        pattern=r"^\d{2}-\d{7}$",
        description="Employer Identification Number (XX-XXXXXXX format)",
    )

    # User details
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    name: str | None = Field(default=None, max_length=255, description="Full name")


class LoginRequest(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Schema for token refresh."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Schema for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Public user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    role: str
    organization_id: UUID
    is_active: bool
    is_verified: bool
    last_login_at: datetime | None
    created_at: datetime
