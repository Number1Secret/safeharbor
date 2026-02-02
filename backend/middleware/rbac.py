"""
Role-Based Access Control Middleware

Manages roles, permissions, and authorization for multi-tenant access.
"""

import logging
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """System roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"
    API_KEY = "api_key"


class Permission(str, Enum):
    """Granular permissions."""
    # Organizations
    ORG_READ = "org:read"
    ORG_WRITE = "org:write"
    ORG_DELETE = "org:delete"

    # Employees
    EMPLOYEE_READ = "employee:read"
    EMPLOYEE_WRITE = "employee:write"
    EMPLOYEE_PII = "employee:pii"  # Access to SSN, etc.

    # Calculations
    CALC_READ = "calc:read"
    CALC_CREATE = "calc:create"
    CALC_APPROVE = "calc:approve"
    CALC_FINALIZE = "calc:finalize"

    # Integrations
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"
    INTEGRATION_SYNC = "integration:sync"

    # Write-back
    WRITEBACK_READ = "writeback:read"
    WRITEBACK_APPROVE = "writeback:approve"
    WRITEBACK_EXECUTE = "writeback:execute"

    # Compliance
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_EXPORT = "compliance:export"
    VAULT_READ = "vault:read"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_API_KEYS = "admin:api_keys"
    ADMIN_SSO = "admin:sso"


# Role-permission mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: set(Permission),  # All permissions
    Role.ADMIN: {
        Permission.ORG_READ, Permission.ORG_WRITE,
        Permission.EMPLOYEE_READ, Permission.EMPLOYEE_WRITE, Permission.EMPLOYEE_PII,
        Permission.CALC_READ, Permission.CALC_CREATE, Permission.CALC_APPROVE, Permission.CALC_FINALIZE,
        Permission.INTEGRATION_READ, Permission.INTEGRATION_WRITE, Permission.INTEGRATION_SYNC,
        Permission.WRITEBACK_READ, Permission.WRITEBACK_APPROVE, Permission.WRITEBACK_EXECUTE,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_EXPORT, Permission.VAULT_READ,
        Permission.ADMIN_USERS, Permission.ADMIN_SETTINGS, Permission.ADMIN_API_KEYS,
    },
    Role.MANAGER: {
        Permission.ORG_READ,
        Permission.EMPLOYEE_READ, Permission.EMPLOYEE_WRITE,
        Permission.CALC_READ, Permission.CALC_CREATE, Permission.CALC_APPROVE,
        Permission.INTEGRATION_READ, Permission.INTEGRATION_SYNC,
        Permission.WRITEBACK_READ, Permission.WRITEBACK_APPROVE,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_EXPORT, Permission.VAULT_READ,
    },
    Role.VIEWER: {
        Permission.ORG_READ,
        Permission.EMPLOYEE_READ,
        Permission.CALC_READ,
        Permission.INTEGRATION_READ,
        Permission.WRITEBACK_READ,
        Permission.COMPLIANCE_READ, Permission.VAULT_READ,
    },
    Role.API_KEY: {
        Permission.ORG_READ,
        Permission.EMPLOYEE_READ,
        Permission.CALC_READ, Permission.CALC_CREATE,
        Permission.INTEGRATION_READ,
    },
}


class CurrentUser(BaseModel):
    """Authenticated user context."""
    id: UUID
    email: str
    organization_id: UUID
    role: Role
    permissions: set[Permission] = Field(default_factory=set)
    is_api_key: bool = False

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_any_permission(self, *permissions: Permission) -> bool:
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, *permissions: Permission) -> bool:
        return all(p in self.permissions for p in permissions)


async def get_current_user(request: Request) -> CurrentUser:
    """
    Extract and validate the current user from request.

    Supports:
    - Bearer token (JWT)
    - API key (x-api-key header)
    """
    # Check API key first
    api_key = request.headers.get("x-api-key")
    if api_key:
        return await _validate_api_key(api_key)

    # Check Bearer token
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = auth_header.split(" ", 1)[1]
    return await _validate_token(token)


def require_permission(*permissions: Permission):
    """Dependency that checks for specific permissions."""

    async def check(user: CurrentUser = Depends(get_current_user)):
        for perm in permissions:
            if not user.has_permission(perm):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {perm.value}",
                )
        return user

    return check


def require_role(*roles: Role):
    """Dependency that checks for specific roles."""

    async def check(user: CurrentUser = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Required role: {', '.join(r.value for r in roles)}",
            )
        return user

    return check


def require_org_access(org_id_param: str = "org_id"):
    """Dependency that verifies user has access to the organization."""

    async def check(request: Request, user: CurrentUser = Depends(get_current_user)):
        org_id = request.path_params.get(org_id_param)
        if org_id and str(user.organization_id) != org_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this organization",
            )
        return user

    return check


async def _validate_token(token: str) -> CurrentUser:
    """Validate JWT token and return user context."""
    import jwt

    from backend.config import get_settings

    secret = get_settings().secret_key

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    role = Role(payload.get("role", "viewer"))
    permissions = ROLE_PERMISSIONS.get(role, set())

    return CurrentUser(
        id=UUID(payload["sub"]),
        email=payload.get("email", ""),
        organization_id=UUID(payload["org_id"]),
        role=role,
        permissions=permissions,
    )


async def _validate_api_key(api_key: str) -> CurrentUser:
    """Validate API key by hashing and looking up in the database."""
    import hashlib
    from datetime import datetime, timezone

    from sqlalchemy import select

    from backend.db.session import get_async_session
    from backend.models.api_key import APIKey

    if not api_key.startswith("sh_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with get_async_session() as session:
        result = await session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        db_key = result.scalar_one_or_none()

        if not db_key or not db_key.is_active:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        if db_key.expires_at and db_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="API key has expired")

        # Update last used timestamp
        db_key.last_used_at = datetime.now(timezone.utc)
        await session.commit()

    # Map stored permission strings to Permission enums
    key_permissions: set[Permission] = set()
    for perm_str in db_key.permissions:
        try:
            key_permissions.add(Permission(perm_str))
        except ValueError:
            pass

    return CurrentUser(
        id=db_key.id,
        email=f"api-key:{db_key.key_prefix}",
        organization_id=db_key.organization_id,
        role=Role.API_KEY,
        permissions=key_permissions,
        is_api_key=True,
    )
