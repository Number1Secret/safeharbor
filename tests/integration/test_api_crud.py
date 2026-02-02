"""
Integration Tests for API CRUD Endpoints

Tests cover Organizations, Employees, Calculations, and Admin endpoints
using the async test client, database fixtures, and factory helpers.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.organization import Organization
from backend.models.user import User
from backend.services.auth import create_access_token
from tests.factories import make_calculation_run, make_employee, make_user


# ---------------------------------------------------------------------------
# Organization Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_organization(
    client: AsyncClient,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/organizations/{org_id} returns 200 with correct name and EIN."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_org.name
    assert data["ein"] == "99-9999999"


@pytest.mark.asyncio
async def test_get_organization_no_auth(
    client: AsyncClient,
    test_org: Organization,
) -> None:
    """GET /api/v1/organizations/{org_id} without auth returns 401."""
    response = await client.get(f"/api/v1/organizations/{test_org.id}")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Employee Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_employee(
    client: AsyncClient,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/organizations/{org_id}/employees with valid data returns 201."""
    payload = {
        "first_name": "Jane",
        "last_name": "Smith",
        "ssn": "123-45-6789",
        "hire_date": "2024-01-15",
        "job_title": "Server",
        "department": "Front of House",
        "hourly_rate": 15.00,
        "is_hourly": True,
        "filing_status": "single",
    }

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/employees",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Jane"
    assert data["last_name"] == "Smith"
    assert data["job_title"] == "Server"
    assert data["department"] == "Front of House"


@pytest.mark.asyncio
async def test_list_employees(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/organizations/{org_id}/employees returns 200 with results after creating employees."""
    emp1 = make_employee(test_org.id, first_name="Alice", last_name="Anderson")
    emp2 = make_employee(test_org.id, first_name="Bob", last_name="Brown")
    db_session.add(emp1)
    db_session.add(emp2)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/employees",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    names = {item["first_name"] for item in data["items"]}
    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.asyncio
async def test_get_employee_detail(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/organizations/{org_id}/employees/{employee_id} returns 200."""
    emp = make_employee(test_org.id, first_name="Carlos", last_name="Cruz")
    db_session.add(emp)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/employees/{emp.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Carlos"
    assert data["last_name"] == "Cruz"
    assert data["id"] == str(emp.id)


# ---------------------------------------------------------------------------
# Calculation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_calculation_run(
    client: AsyncClient,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/organizations/{org_id}/calculations returns 201 with status 'pending'."""
    payload = {
        "run_type": "pay_period",
        "period_start": "2025-05-01",
        "period_end": "2025-05-15",
        "tax_year": 2025,
    }

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/calculations",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["organization_id"] == str(test_org.id)


@pytest.mark.asyncio
async def test_get_calculation_run(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/organizations/{org_id}/calculations/{run_id} returns 200 for a factory-created run."""
    run = make_calculation_run(test_org.id)
    db_session.add(run)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/calculations/{run.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(run.id)
    assert data["run_type"] == "regular"


# ---------------------------------------------------------------------------
# Admin Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users(
    client: AsyncClient,
    test_org: Organization,
    test_user: User,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/organizations/{org_id}/admin/users returns 200 with at least the test user."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/admin/users",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    emails = {user["email"] for user in data}
    assert "owner@test.com" in emails


@pytest.mark.asyncio
async def test_create_api_key(
    client: AsyncClient,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/organizations/{org_id}/admin/api-keys returns 201 with a key value."""
    payload = {
        "name": "CI/CD Key",
    }

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/admin/api-keys",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert "full_key" in data
    assert data["full_key"].startswith("sh_")
    assert data["name"] == "CI/CD Key"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_api_keys(
    client: AsyncClient,
    test_org: Organization,
    auth_headers: dict[str, str],
) -> None:
    """After creating an API key, GET /api/v1/organizations/{org_id}/admin/api-keys returns it."""
    # Create a key first
    create_response = await client.post(
        f"/api/v1/organizations/{test_org.id}/admin/api-keys",
        json={"name": "List Test Key"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    created_key = create_response.json()

    # List keys
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/admin/api-keys",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    key_names = {key["name"] for key in data}
    assert "List Test Key" in key_names

    # Verify the created key appears in the list by ID
    key_ids = {key["id"] for key in data}
    assert created_key["id"] in key_ids


@pytest.mark.asyncio
async def test_admin_access_denied_for_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """A user with 'viewer' role cannot access admin endpoints and receives 403."""
    viewer_user = make_user(
        test_org.id,
        email="viewer@test.com",
        role="viewer",
    )
    db_session.add(viewer_user)
    await db_session.flush()

    viewer_token = create_access_token(
        sub=str(viewer_user.id),
        email=viewer_user.email,
        org_id=str(test_org.id),
        role="viewer",
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/admin/users",
        headers=viewer_headers,
    )

    assert response.status_code == 403
