"""
Test Configuration and Fixtures

Provides async test client, database fixtures, and authentication helpers.
"""

import asyncio
import hashlib
import secrets
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.session import get_db
from backend.main import app
from backend.models.base import Base
from backend.models.api_key import APIKey
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password

settings = get_settings()

# Use a separate test database
TEST_DATABASE_URL = settings.database_url.replace("/safeharbor", "/safeharbor_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client with dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    org = Organization(
        id=uuid4(),
        name="Test Org",
        ein="99-9999999",
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
async def test_user(db_session: AsyncSession, test_org: Organization) -> User:
    """Create a test owner user."""
    user = User(
        id=uuid4(),
        organization_id=test_org.id,
        email="owner@test.com",
        name="Test Owner",
        hashed_password=hash_password("TestPass123!"),
        role="owner",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User, test_org: Organization) -> dict[str, str]:
    """Generate JWT auth headers for the test user."""
    token = create_access_token(
        sub=str(test_user.id),
        email=test_user.email,
        org_id=str(test_org.id),
        role=test_user.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_api_key(
    db_session: AsyncSession, test_org: Organization, test_user: User
) -> tuple[APIKey, str]:
    """Create a test API key, returns (db_record, raw_key)."""
    raw_key = "sh_" + secrets.token_urlsafe(32)
    key = APIKey(
        id=uuid4(),
        organization_id=test_org.id,
        created_by=test_user.id,
        name="Test Key",
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        key_prefix=raw_key[:12] + "...",
        permissions=["org:read", "employee:read", "calc:read"],
        is_active=True,
    )
    db_session.add(key)
    await db_session.flush()
    return key, raw_key
