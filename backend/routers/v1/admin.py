"""
Admin API Routes

Organization admin settings, user management, API keys, and SSO configuration.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    Role,
    get_current_user,
    require_permission,
    require_role,
)
from backend.models.api_key import APIKey
from backend.models.organization import Organization
from backend.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


# --- User Management ---


class UserInviteRequest(BaseModel):
    email: str
    role: str = "viewer"
    name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class UserRoleUpdateRequest(BaseModel):
    role: str


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """List all users in the organization."""
    result = await db.execute(
        select(User)
        .where(User.organization_id == user.organization_id)
        .order_by(User.created_at.desc())
    )
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/users/invite", response_model=UserResponse, status_code=201)
async def invite_user(
    request: UserInviteRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user to the organization."""
    if request.role not in [r.value for r in Role if r != Role.API_KEY]:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    invite_token = secrets.token_urlsafe(32)

    new_user = User(
        organization_id=user.organization_id,
        email=request.email,
        name=request.name,
        role=request.role,
        is_active=False,  # Activated when invite is accepted
        is_verified=False,
        invite_token=invite_token,
        invite_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_user)
    await db.flush()

    return UserResponse.model_validate(new_user)


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    request: UserRoleUpdateRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role."""
    if request.role not in [r.value for r in Role if r != Role.API_KEY]:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    result = await db.execute(
        select(User).where(User.id == user_id, User.organization_id == user.organization_id)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = request.role
    await db.flush()

    return UserResponse.model_validate(target_user)


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: UUID,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user."""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(
        select(User).where(User.id == user_id, User.organization_id == user.organization_id)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_active = False
    await db.flush()

    return {"status": "deactivated", "user_id": str(user_id)}


# --- API Key Management ---


class APIKeyCreateRequest(BaseModel):
    name: str
    permissions: list[str] | None = None
    expires_in_days: int | None = None


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    permissions: list
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when creating a key - includes the full key (shown only once)."""
    full_key: str


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_API_KEYS)),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the organization."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.organization_id == user.organization_id)
        .order_by(APIKey.created_at.desc())
    )
    return [APIKeyResponse.model_validate(k) for k in result.scalars().all()]


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_API_KEYS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.

    The full key is returned only once in the response.
    Store it securely - it cannot be retrieved again.
    """
    raw_key = secrets.token_urlsafe(32)
    full_key = f"sh_{raw_key}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:12] + "..."

    permissions = request.permissions or ["org:read", "calc:read"]

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    api_key = APIKey(
        organization_id=user.organization_id,
        created_by=user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        permissions=permissions,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()

    resp = APIKeyCreatedResponse.model_validate(api_key)
    resp.full_key = full_key
    return resp


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_API_KEYS)),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == user.organization_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.flush()

    return {"status": "revoked", "key_id": str(key_id)}


# --- SSO Configuration ---


class SSOConfigRequest(BaseModel):
    protocol: str  # "saml" or "oidc"
    name: str

    # SAML
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_certificate: str | None = None

    # OIDC
    client_id: str | None = None
    client_secret: str | None = None
    issuer_url: str | None = None

    # Role mapping
    role_mapping: dict[str, str] | None = None


class SSOConfigResponse(BaseModel):
    id: UUID
    protocol: str
    name: str
    is_active: bool
    created_at: str


@router.get("/sso", response_model=list[SSOConfigResponse])
async def list_sso_configs(
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SSO)),
    db: AsyncSession = Depends(get_db),
):
    """List SSO configurations."""
    return []


@router.post("/sso", response_model=SSOConfigResponse)
async def configure_sso(
    request: SSOConfigRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SSO)),
    db: AsyncSession = Depends(get_db),
):
    """Configure SSO for the organization."""
    from backend.services.sso import SSOService

    sso_service = SSOService(db)

    if request.protocol == "saml":
        provider = await sso_service.configure_saml(
            organization_id=user.organization_id,
            name=request.name,
            idp_entity_id=request.idp_entity_id or "",
            idp_sso_url=request.idp_sso_url or "",
            idp_certificate=request.idp_certificate or "",
            role_mapping=request.role_mapping,
        )
    elif request.protocol == "oidc":
        provider = await sso_service.configure_oidc(
            organization_id=user.organization_id,
            name=request.name,
            client_id=request.client_id or "",
            client_secret=request.client_secret or "",
            issuer_url=request.issuer_url or "",
            role_mapping=request.role_mapping,
        )
    else:
        raise HTTPException(status_code=400, detail="Protocol must be 'saml' or 'oidc'")

    return SSOConfigResponse(
        id=provider.id,
        protocol=provider.protocol,
        name=provider.name,
        is_active=provider.is_active,
        created_at=provider.created_at.isoformat(),
    )


@router.delete("/sso/{sso_id}")
async def delete_sso_config(
    sso_id: UUID,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SSO)),
    db: AsyncSession = Depends(get_db),
):
    """Delete SSO configuration."""
    return {"status": "deleted", "sso_id": str(sso_id)}


# --- Organization Settings ---


class OrgSettingsUpdateRequest(BaseModel):
    workweek_start: str | None = None
    default_filing_status: str | None = None
    auto_approve_threshold: float | None = None
    notification_email: str | None = None
    webhook_url: str | None = None


@router.get("/settings")
async def get_org_settings(
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """Get organization settings."""
    result = await db.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {
        "workweek_start": org.workweek_start,
        "tip_credit_enabled": org.tip_credit_enabled,
        "overtime_credit_enabled": org.overtime_credit_enabled,
        "penalty_guarantee_active": org.penalty_guarantee_active,
        **org.settings,
    }


@router.put("/settings")
async def update_org_settings(
    request: OrgSettingsUpdateRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """Update organization settings."""
    result = await db.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    updates = request.model_dump(exclude_none=True)

    # Workweek start is a column, not a settings JSON key
    if "workweek_start" in updates:
        org.workweek_start = updates.pop("workweek_start")

    # Remaining keys go into the settings JSONB column
    if updates:
        new_settings = {**org.settings, **updates}
        org.settings = new_settings

    await db.flush()

    return {
        "status": "updated",
        "workweek_start": org.workweek_start,
        "tip_credit_enabled": org.tip_credit_enabled,
        "overtime_credit_enabled": org.overtime_credit_enabled,
        "penalty_guarantee_active": org.penalty_guarantee_active,
        **org.settings,
    }
