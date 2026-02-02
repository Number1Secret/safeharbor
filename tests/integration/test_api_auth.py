"""Integration tests for the auth API endpoints at /api/v1/auth."""

import pytest

BASE = "http://test/api/v1/auth"


def _register_payload(
    email: str = "newuser@example.com",
    ein: str = "11-1111111",
    org_name: str = "New Org",
    password: str = "SecurePass1!",
    name: str = "New User",
) -> dict:
    return {
        "org_name": org_name,
        "ein": ein,
        "email": email,
        "password": password,
        "name": name,
    }


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_register_success(client):
    """Register a new org+user and receive 201 with access and refresh tokens."""
    payload = _register_payload(
        email="fresh@example.com",
        ein="11-1111111",
        org_name="Fresh Org",
    )
    response = await client.post(f"{BASE}/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["expires_in"], int)


@pytest.mark.asyncio
async def test_register_duplicate_email(client, test_user):
    """Registering with an already-taken email returns 409."""
    payload = _register_payload(
        email="owner@test.com",  # same as test_user
        ein="22-2222222",
        org_name="Duplicate Email Org",
    )
    response = await client.post(f"{BASE}/register", json=payload)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_ein(client, test_org):
    """Registering with an already-taken EIN returns 409."""
    payload = _register_payload(
        email="unique@example.com",
        ein="99-9999999",  # same as test_org
        org_name="Duplicate EIN Org",
    )
    response = await client.post(f"{BASE}/register", json=payload)

    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    """Logging in with valid credentials returns 200 and tokens."""
    response = await client.post(
        f"{BASE}/login",
        json={"email": "owner@test.com", "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["expires_in"], int)


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    """Logging in with the wrong password returns 401."""
    response = await client.post(
        f"{BASE}/login",
        json={"email": "owner@test.com", "password": "WrongPassword99!"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    """Logging in with an email that does not exist returns 401."""
    response = await client.post(
        f"{BASE}/login",
        json={"email": "nobody@nowhere.com", "password": "DoesNotMatter1!"},
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Token refresh
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_refresh_token_success(client, test_user):
    """Using a valid refresh token returns 200 and a new token pair."""
    # First, login to obtain tokens.
    login_resp = await client.post(
        f"{BASE}/login",
        json={"email": "owner@test.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Use the refresh token.
    response = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token(client, test_user):
    """Passing an access token where a refresh token is expected returns 401."""
    login_resp = await client.post(
        f"{BASE}/login",
        json={"email": "owner@test.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    response = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Change password
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_change_password_success(client, test_user, auth_headers):
    """Changing password with the correct current password returns 204."""
    response = await client.post(
        f"{BASE}/change-password",
        json={
            "current_password": "TestPass123!",
            "new_password": "NewSecure456!",
        },
        headers=auth_headers,
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, test_user, auth_headers):
    """Providing the wrong current password returns 401."""
    response = await client.post(
        f"{BASE}/change-password",
        json={
            "current_password": "TotallyWrong0!",
            "new_password": "NewSecure456!",
        },
        headers=auth_headers,
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# GET /me
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_me_success(client, test_user, auth_headers):
    """GET /me with valid auth returns 200 and the authenticated user's data."""
    response = await client.get(f"{BASE}/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "owner@test.com"
    assert data["role"] == "owner"
    assert "id" in data
    assert "organization_id" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_no_auth(client):
    """GET /me without an Authorization header returns 401."""
    response = await client.get(f"{BASE}/me")

    assert response.status_code == 401
