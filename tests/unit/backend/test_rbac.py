"""
Unit Tests for RBAC Middleware

Tests role-permission mappings, CurrentUser helper methods,
and JWT token validation logic.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from backend.config import get_settings
from backend.middleware.rbac import (
    ROLE_PERMISSIONS,
    CurrentUser,
    Permission,
    Role,
    _validate_token,
)
from backend.services.auth import create_access_token

settings = get_settings()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: Role, permissions: set[Permission] | None = None) -> CurrentUser:
    """Build a CurrentUser with role-based permissions (or explicit overrides)."""
    return CurrentUser(
        id=uuid4(),
        email="test@example.com",
        organization_id=uuid4(),
        role=role,
        permissions=permissions if permissions is not None else ROLE_PERMISSIONS[role],
    )


# ===========================================================================
# 1-5  Role-permission mapping tests
# ===========================================================================

class TestRolePermissions:
    """Verify that ROLE_PERMISSIONS grants the correct capabilities."""

    def test_owner_has_all_permissions(self):
        """Test 1: OWNER role must possess every defined permission."""
        owner_perms = ROLE_PERMISSIONS[Role.OWNER]
        all_perms = set(Permission)
        assert owner_perms == all_perms, (
            f"OWNER is missing: {all_perms - owner_perms}"
        )

    def test_admin_has_expected_permissions_subset(self):
        """Test 2: ADMIN should have all permissions except ORG_DELETE and ADMIN_SSO."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        excluded = {Permission.ORG_DELETE, Permission.ADMIN_SSO}
        expected = set(Permission) - excluded
        assert admin_perms == expected, (
            f"ADMIN extra: {admin_perms - expected}; missing: {expected - admin_perms}"
        )

    def test_manager_can_approve_but_not_finalize(self):
        """Test 3: MANAGER should be able to approve calculations but not finalize them."""
        manager_perms = ROLE_PERMISSIONS[Role.MANAGER]
        assert Permission.CALC_APPROVE in manager_perms, (
            "MANAGER must have CALC_APPROVE"
        )
        assert Permission.CALC_FINALIZE not in manager_perms, (
            "MANAGER must NOT have CALC_FINALIZE"
        )

    def test_viewer_has_only_read_permissions(self):
        """Test 4: VIEWER should have only read-level permissions."""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        expected = {
            Permission.ORG_READ,
            Permission.EMPLOYEE_READ,
            Permission.CALC_READ,
            Permission.INTEGRATION_READ,
            Permission.WRITEBACK_READ,
            Permission.COMPLIANCE_READ,
            Permission.VAULT_READ,
        }
        assert viewer_perms == expected, (
            f"VIEWER extra: {viewer_perms - expected}; missing: {expected - viewer_perms}"
        )
        # Double-check that every permission is a read-type permission
        for perm in viewer_perms:
            assert perm.value.endswith(":read"), (
                f"VIEWER permission {perm.value} is not read-only"
            )

    def test_api_key_has_limited_permissions(self):
        """Test 5: API_KEY role should have a narrow, well-defined permission set."""
        api_key_perms = ROLE_PERMISSIONS[Role.API_KEY]
        expected = {
            Permission.ORG_READ,
            Permission.EMPLOYEE_READ,
            Permission.CALC_READ,
            Permission.CALC_CREATE,
            Permission.INTEGRATION_READ,
        }
        assert api_key_perms == expected, (
            f"API_KEY extra: {api_key_perms - expected}; missing: {expected - api_key_perms}"
        )
        # Ensure no write/admin permissions leaked in
        write_or_admin = {
            p for p in Permission
            if "write" in p.value or "admin" in p.value or "delete" in p.value
        }
        assert api_key_perms.isdisjoint(write_or_admin), (
            f"API_KEY must not have write/admin permissions: {api_key_perms & write_or_admin}"
        )


# ===========================================================================
# 6-8  CurrentUser helper method tests
# ===========================================================================

class TestCurrentUserHelpers:
    """Verify the convenience permission-checking methods on CurrentUser."""

    def test_has_permission(self):
        """Test 6: has_permission returns True only for granted permissions."""
        user = _make_user(Role.VIEWER)
        assert user.has_permission(Permission.ORG_READ) is True
        assert user.has_permission(Permission.ORG_WRITE) is False
        assert user.has_permission(Permission.CALC_FINALIZE) is False

    def test_has_any_permission(self):
        """Test 7: has_any_permission returns True when at least one matches."""
        user = _make_user(Role.VIEWER)
        # One match, one miss
        assert user.has_any_permission(Permission.ORG_READ, Permission.ORG_WRITE) is True
        # Both miss
        assert user.has_any_permission(Permission.ORG_WRITE, Permission.ORG_DELETE) is False
        # Both match
        assert user.has_any_permission(Permission.ORG_READ, Permission.CALC_READ) is True

    def test_has_all_permissions(self):
        """Test 8: has_all_permissions returns True only when every permission matches."""
        user = _make_user(Role.VIEWER)
        # All present
        assert user.has_all_permissions(Permission.ORG_READ, Permission.CALC_READ) is True
        # One missing
        assert user.has_all_permissions(Permission.ORG_READ, Permission.ORG_WRITE) is False
        # All missing
        assert user.has_all_permissions(Permission.ORG_WRITE, Permission.ORG_DELETE) is False


# ===========================================================================
# 9-11  _validate_token tests (async)
# ===========================================================================

class TestValidateToken:
    """Exercise the JWT validation path in _validate_token."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_correct_user(self):
        """Test 9: A well-formed JWT should produce a CurrentUser with correct fields."""
        user_id = uuid4()
        org_id = uuid4()
        email = "admin@safeharbor.test"
        role = Role.ADMIN

        token = create_access_token(
            sub=str(user_id),
            email=email,
            org_id=str(org_id),
            role=role.value,
        )

        current_user = await _validate_token(token)

        assert current_user.id == user_id
        assert current_user.email == email
        assert current_user.organization_id == org_id
        assert current_user.role == Role.ADMIN
        assert current_user.permissions == ROLE_PERMISSIONS[Role.ADMIN]
        assert current_user.is_api_key is False

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Test 10: A malformed or wrongly-signed JWT should raise HTTPException 401."""
        from fastapi import HTTPException

        # Completely invalid string
        with pytest.raises(HTTPException) as exc_info:
            await _validate_token("this.is.not.a.jwt")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

        # Valid JWT structure but signed with the wrong secret
        wrong_secret_token = jwt.encode(
            {
                "sub": str(uuid4()),
                "email": "bad@test.com",
                "org_id": str(uuid4()),
                "role": "viewer",
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "wrong-secret-key",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc_info:
            await _validate_token(wrong_secret_token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Test 11: An expired JWT should raise HTTPException 401."""
        from fastapi import HTTPException

        expired_token = jwt.encode(
            {
                "sub": str(uuid4()),
                "email": "expired@test.com",
                "org_id": str(uuid4()),
                "role": "viewer",
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            settings.secret_key,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            await _validate_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail
