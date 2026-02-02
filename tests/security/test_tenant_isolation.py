"""
Multi-Tenant Data Isolation Tests

Verifies that users in Organization A cannot access
Organization B's resources across all API endpoints.
"""

import hashlib
import secrets
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.employee import Employee
from backend.models.integration import Integration
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from tests.factories import make_calculation_run, make_employee, make_integration


@pytest_asyncio.fixture
async def org_a(db_session: AsyncSession) -> Organization:
    """Organization A."""
    org = Organization(
        id=uuid4(),
        name="Org Alpha",
        ein="10-1000001",
        tax_year=2025,
        tier="pro",
        tip_credit_enabled=True,
        overtime_credit_enabled=True,
        status="active",
        workweek_start="monday",
        settings={},
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest_asyncio.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    """Organization B."""
    org = Organization(
        id=uuid4(),
        name="Org Bravo",
        ein="20-2000002",
        tax_year=2025,
        tier="pro",
        tip_credit_enabled=True,
        overtime_credit_enabled=True,
        status="active",
        workweek_start="sunday",
        settings={},
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, org_a: Organization) -> User:
    """Owner of Org A."""
    user = User(
        id=uuid4(),
        organization_id=org_a.id,
        email="owner@alpha.com",
        name="Alpha Owner",
        hashed_password=hash_password("AlphaPass1!"),
        role="owner",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, org_b: Organization) -> User:
    """Owner of Org B."""
    user = User(
        id=uuid4(),
        organization_id=org_b.id,
        email="owner@bravo.com",
        name="Bravo Owner",
        hashed_password=hash_password("BravoPass1!"),
        role="owner",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
def headers_a(user_a: User, org_a: Organization) -> dict:
    """Auth headers for Org A user."""
    token = create_access_token(
        sub=str(user_a.id),
        email=user_a.email,
        org_id=str(org_a.id),
        role=user_a.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def headers_b(user_b: User, org_b: Organization) -> dict:
    """Auth headers for Org B user."""
    token = create_access_token(
        sub=str(user_b.id),
        email=user_b.email,
        org_id=str(org_b.id),
        role=user_b.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def employee_b(db_session: AsyncSession, org_b: Organization) -> Employee:
    """Employee belonging to Org B."""
    emp = make_employee(org_b.id, first_name="Bravo", last_name="Employee")
    db_session.add(emp)
    await db_session.flush()
    return emp


@pytest_asyncio.fixture
async def integration_b(db_session: AsyncSession, org_b: Organization) -> Integration:
    """Integration belonging to Org B."""
    integ = make_integration(org_b.id, provider="gusto")
    db_session.add(integ)
    await db_session.flush()
    return integ


# ── Organization Access Tests ─────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_read_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to read Org B's details."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_update_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to update Org B."""
    resp = await client.patch(
        f"http://test/api/v1/organizations/{org_b.id}",
        headers=headers_a,
        json={"name": "Hacked Name"},
    )
    assert resp.status_code == 403


# ── Employee Access Tests ─────────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_list_org_b_employees(
    client: AsyncClient, headers_a: dict, org_b: Organization, employee_b: Employee,
):
    """User A should not be able to list Org B's employees."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/employees",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_read_org_b_employee(
    client: AsyncClient, headers_a: dict, org_b: Organization, employee_b: Employee,
):
    """User A should not be able to read a specific Org B employee."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/employees/{employee_b.id}",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_create_employee_in_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to create an employee in Org B."""
    resp = await client.post(
        f"http://test/api/v1/organizations/{org_b.id}/employees",
        headers=headers_a,
        json={
            "first_name": "Injected",
            "last_name": "Employee",
            "ssn": "999-99-9999",
            "hire_date": "2024-01-01",
            "job_title": "Attacker",
        },
    )
    assert resp.status_code == 403


# ── Calculation Access Tests ──────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_create_calc_in_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to create a calculation run in Org B."""
    resp = await client.post(
        f"http://test/api/v1/organizations/{org_b.id}/calculations",
        headers=headers_a,
        json={
            "run_type": "pay_period",
            "period_start": "2025-05-01",
            "period_end": "2025-05-15",
        },
    )
    assert resp.status_code == 403


# ── Integration Access Tests ──────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_list_org_b_integrations(
    client: AsyncClient, headers_a: dict, org_b: Organization, integration_b: Integration,
):
    """User A should not be able to list Org B's integrations."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/integrations",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_trigger_sync_on_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization, integration_b: Integration,
):
    """User A should not be able to trigger a sync for Org B's integration."""
    resp = await client.post(
        f"http://test/api/v1/organizations/{org_b.id}/integrations/{integration_b.id}/sync",
        headers=headers_a,
    )
    assert resp.status_code == 403


# ── Admin Access Tests ────────────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_list_org_b_users(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to list Org B's users."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/admin/users",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_cannot_create_api_key_for_org_b(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to create an API key for Org B."""
    resp = await client.post(
        f"http://test/api/v1/organizations/{org_b.id}/admin/api-keys",
        headers=headers_a,
        json={"name": "Stolen Key"},
    )
    assert resp.status_code == 403


# ── Compliance Access Tests ───────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_access_org_b_vault(
    client: AsyncClient, headers_a: dict, org_b: Organization,
):
    """User A should not be able to access Org B's compliance vault."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/compliance/vault",
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_b_can_access_own_resources(
    client: AsyncClient, headers_b: dict, org_b: Organization, employee_b: Employee,
):
    """Verify that Org B's owner CAN access their own resources (sanity check)."""
    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}",
        headers=headers_b,
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"http://test/api/v1/organizations/{org_b.id}/employees",
        headers=headers_b,
    )
    assert resp.status_code == 200
