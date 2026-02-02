"""
Test Factories

Helper functions for creating model instances in tests.
"""

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from backend.models.api_key import APIKey
from backend.models.calculation_run import CalculationRun
from backend.models.employee import Employee
from backend.models.integration import Integration
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.auth import hash_password


def make_organization(**overrides) -> Organization:
    """Create an Organization instance with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "name": "Test Restaurant Inc.",
        "ein": f"{secrets.randbelow(90) + 10}-{secrets.randbelow(9000000) + 1000000}",
        "tax_year": 2025,
        "tier": "pro",
        "tip_credit_enabled": True,
        "overtime_credit_enabled": True,
        "status": "active",
        "workweek_start": "monday",
        "settings": {},
    }
    defaults.update(overrides)
    return Organization(**defaults)


def make_user(organization_id, **overrides) -> User:
    """Create a User instance with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "organization_id": organization_id,
        "email": f"user-{secrets.token_hex(4)}@test.com",
        "name": "Test User",
        "hashed_password": hash_password("TestPassword123!"),
        "role": "viewer",
        "is_active": True,
        "is_verified": True,
    }
    defaults.update(overrides)
    return User(**defaults)


def make_employee(organization_id, **overrides) -> Employee:
    """Create an Employee instance with sensible defaults."""
    first = overrides.pop("first_name", "John")
    last = overrides.pop("last_name", "Doe")
    defaults = {
        "id": uuid4(),
        "organization_id": organization_id,
        "first_name": first,
        "last_name": last,
        "ssn_hash": hashlib.sha256(f"ssn-{secrets.token_hex(4)}".encode()).hexdigest(),
        "hire_date": date(2024, 1, 15),
        "job_title": "Server",
        "department": "Front of House",
        "hourly_rate": Decimal("15.00"),
        "is_hourly": True,
        "filing_status": "single",
        "estimated_annual_magi": Decimal("30000"),
        "employment_status": "active",
    }
    defaults.update(overrides)
    return Employee(**defaults)


def make_integration(organization_id, **overrides) -> Integration:
    """Create an Integration instance with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "organization_id": organization_id,
        "provider": "gusto",
        "provider_category": "payroll",
        "status": "connected",
        "scopes": [],
    }
    defaults.update(overrides)
    return Integration(**defaults)


def make_calculation_run(organization_id, **overrides) -> CalculationRun:
    """Create a CalculationRun instance with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "organization_id": organization_id,
        "run_type": "regular",
        "period_start": date(2025, 5, 1),
        "period_end": date(2025, 5, 15),
        "tax_year": 2025,
        "total_employees": 10,
        "processed_employees": 0,
        "status": "pending",
        "engine_versions": {"premium_engine": "v1.0.0"},
    }
    defaults.update(overrides)
    return CalculationRun(**defaults)


def make_api_key(organization_id, created_by, **overrides) -> tuple[APIKey, str]:
    """Create an APIKey instance with sensible defaults. Returns (key, raw_key)."""
    raw_key = "sh_" + secrets.token_urlsafe(32)
    defaults = {
        "id": uuid4(),
        "organization_id": organization_id,
        "created_by": created_by,
        "name": "Test API Key",
        "key_hash": hashlib.sha256(raw_key.encode()).hexdigest(),
        "key_prefix": raw_key[:12] + "...",
        "permissions": ["org:read", "calc:read"],
        "is_active": True,
    }
    defaults.update(overrides)
    return APIKey(**defaults), raw_key
