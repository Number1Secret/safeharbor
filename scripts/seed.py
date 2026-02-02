"""
Seed Script

Populates the database with demo data for development and testing.
Creates "Bella's Restaurant Group" organization with employees,
integrations, calculation runs, and vault entries.

Usage:
    python -m scripts.seed
"""

import asyncio
import hashlib
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from backend.config import get_settings
from backend.db.session import get_async_session
from backend.models.api_key import APIKey
from backend.models.calculation_run import CalculationRun
from backend.models.employee import Employee
from backend.models.integration import Integration
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.auth import hash_password

settings = get_settings()


async def seed():
    """Create demo data."""
    async with get_async_session() as db:
        # ── Organization ──────────────────────────────────
        org = Organization(
            id=uuid4(),
            name="Bella's Restaurant Group",
            ein="12-3456789",
            tax_year=2025,
            tier="pro",
            tip_credit_enabled=True,
            overtime_credit_enabled=True,
            penalty_guarantee_active=False,
            status="active",
            workweek_start="monday",
            settings={
                "default_filing_status": "single",
                "auto_approve_threshold": 0.95,
            },
            primary_contact_email="bella@bellasrestaurants.com",
            primary_contact_name="Bella Torres",
            onboarded_at=datetime.utcnow() - timedelta(days=30),
        )
        db.add(org)
        await db.flush()

        # ── Admin User ────────────────────────────────────
        admin_user = User(
            id=uuid4(),
            organization_id=org.id,
            email="admin@bellasrestaurants.com",
            name="Bella Torres",
            hashed_password=hash_password("SafeHarbor2025!"),
            role="owner",
            is_active=True,
            is_verified=True,
            last_login_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.add(admin_user)

        manager_user = User(
            id=uuid4(),
            organization_id=org.id,
            email="manager@bellasrestaurants.com",
            name="Carlos Rivera",
            hashed_password=hash_password("Manager2025!"),
            role="manager",
            is_active=True,
            is_verified=True,
        )
        db.add(manager_user)

        await db.flush()

        # ── API Key ───────────────────────────────────────
        raw_key = "sh_" + secrets.token_urlsafe(32)
        api_key = APIKey(
            id=uuid4(),
            organization_id=org.id,
            created_by=admin_user.id,
            name="Development API Key",
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
            key_prefix=raw_key[:12] + "...",
            permissions=["org:read", "employee:read", "calc:read", "calc:create"],
            is_active=True,
        )
        db.add(api_key)

        # ── Employees (10) ────────────────────────────────
        employees_data = [
            {
                "first_name": "Maria", "last_name": "Gonzalez",
                "job_title": "Head Chef", "department": "Kitchen",
                "hourly_rate": Decimal("28.00"), "is_hourly": True,
                "filing_status": "married_joint",
                "estimated_annual_magi": Decimal("58240"),
                "ttoc_code": "35101", "ttoc_title": "cook",
                "employment_status": "active",
                "ytd_gross_wages": Decimal("26880"), "ytd_overtime_hours": Decimal("48"),
                "ytd_qualified_ot_premium": Decimal("672"),
            },
            {
                "first_name": "James", "last_name": "Chen",
                "job_title": "Server", "department": "Front of House",
                "hourly_rate": Decimal("7.25"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("38000"),
                "ttoc_code": "12401", "ttoc_title": "server",
                "employment_status": "active",
                "ytd_gross_wages": Decimal("6960"), "ytd_tips": Decimal("12400"),
                "ytd_qualified_tips": Decimal("12400"),
            },
            {
                "first_name": "Sarah", "last_name": "Johnson",
                "job_title": "Bartender", "department": "Bar",
                "hourly_rate": Decimal("9.50"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("42000"),
                "ttoc_code": "12401", "ttoc_title": "bartender",
                "employment_status": "active",
                "ytd_gross_wages": Decimal("9120"), "ytd_tips": Decimal("15200"),
                "ytd_qualified_tips": Decimal("15200"),
                "ytd_overtime_hours": Decimal("24"),
            },
            {
                "first_name": "David", "last_name": "Williams",
                "job_title": "Sous Chef", "department": "Kitchen",
                "hourly_rate": Decimal("22.00"), "is_hourly": True,
                "filing_status": "married_joint",
                "estimated_annual_magi": Decimal("48000"),
                "ttoc_code": "35101", "employment_status": "active",
                "ytd_gross_wages": Decimal("21120"), "ytd_overtime_hours": Decimal("36"),
                "ytd_qualified_ot_premium": Decimal("396"),
            },
            {
                "first_name": "Emily", "last_name": "Davis",
                "job_title": "Host/Hostess", "department": "Front of House",
                "hourly_rate": Decimal("14.00"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("29120"),
                "employment_status": "active",
                "ytd_gross_wages": Decimal("13440"),
            },
            {
                "first_name": "Michael", "last_name": "Brown",
                "job_title": "Line Cook", "department": "Kitchen",
                "hourly_rate": Decimal("17.50"), "is_hourly": True,
                "filing_status": "head_of_household",
                "estimated_annual_magi": Decimal("40000"),
                "ttoc_code": "35101", "employment_status": "active",
                "ytd_gross_wages": Decimal("16800"), "ytd_overtime_hours": Decimal("52"),
                "ytd_qualified_ot_premium": Decimal("455"),
            },
            {
                "first_name": "Jessica", "last_name": "Martinez",
                "job_title": "Server", "department": "Front of House",
                "hourly_rate": Decimal("7.25"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("35000"),
                "ttoc_code": "12401", "employment_status": "active",
                "ytd_gross_wages": Decimal("6960"), "ytd_tips": Decimal("11000"),
                "ytd_qualified_tips": Decimal("11000"),
            },
            {
                "first_name": "Robert", "last_name": "Taylor",
                "job_title": "Dishwasher", "department": "Kitchen",
                "hourly_rate": Decimal("12.00"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("24960"),
                "employment_status": "active",
                "ytd_gross_wages": Decimal("11520"),
            },
            {
                "first_name": "Amanda", "last_name": "Wilson",
                "job_title": "General Manager", "department": "Management",
                "hourly_rate": Decimal("35.00"), "is_hourly": False,
                "filing_status": "married_joint",
                "estimated_annual_magi": Decimal("72800"),
                "employment_status": "active",
                "ytd_gross_wages": Decimal("33600"),
            },
            {
                "first_name": "Daniel", "last_name": "Anderson",
                "job_title": "Prep Cook", "department": "Kitchen",
                "hourly_rate": Decimal("14.00"), "is_hourly": True,
                "filing_status": "single",
                "estimated_annual_magi": Decimal("29120"),
                "ttoc_code": "35101", "employment_status": "terminated",
                "ytd_gross_wages": Decimal("8400"),
            },
        ]

        for emp_data in employees_data:
            ssn_hash = hashlib.sha256(f"fake-ssn-{emp_data['first_name']}".encode()).hexdigest()
            employee = Employee(
                id=uuid4(),
                organization_id=org.id,
                ssn_hash=ssn_hash,
                hire_date=date(2024, 1, 15),
                **emp_data,
            )
            db.add(employee)

        await db.flush()

        # ── Integrations (3) ──────────────────────────────
        integrations_data = [
            {
                "provider": "gusto", "provider_category": "payroll",
                "display_name": "Gusto Payroll",
                "status": "connected",
                "last_sync_at": datetime.utcnow() - timedelta(hours=1),
                "last_sync_status": "success", "last_sync_records": 10,
            },
            {
                "provider": "toast", "provider_category": "pos",
                "display_name": "Toast POS",
                "status": "connected",
                "last_sync_at": datetime.utcnow() - timedelta(minutes=15),
                "last_sync_status": "success", "last_sync_records": 48,
            },
            {
                "provider": "deputy", "provider_category": "timekeeping",
                "display_name": "Deputy Timekeeping",
                "status": "pending",
            },
        ]

        for int_data in integrations_data:
            integration = Integration(
                id=uuid4(),
                organization_id=org.id,
                scopes=[],
                **int_data,
            )
            db.add(integration)

        # ── Calculation Runs (2) ──────────────────────────
        run1 = CalculationRun(
            id=uuid4(),
            organization_id=org.id,
            run_type="quarterly",
            period_start=date(2025, 5, 1),
            period_end=date(2025, 5, 15),
            tax_year=2025,
            total_employees=10,
            processed_employees=10,
            status="finalized",
            total_qualified_ot_premium=Decimal("1523.00"),
            total_qualified_tips=Decimal("38600.00"),
            total_combined_credit=Decimal("40123.00"),
            engine_versions={"premium_engine": "v1.0.0", "occupation_ai": "v1.0.0"},
        )
        db.add(run1)

        run2 = CalculationRun(
            id=uuid4(),
            organization_id=org.id,
            run_type="quarterly",
            period_start=date(2025, 5, 16),
            period_end=date(2025, 5, 31),
            tax_year=2025,
            total_employees=9,
            processed_employees=5,
            status="calculating",
            engine_versions={"premium_engine": "v1.0.0", "occupation_ai": "v1.0.0"},
        )
        db.add(run2)

        await db.flush()

        print(f"Seeded organization: {org.name} (ID: {org.id})")
        print(f"Admin user: {admin_user.email} / SafeHarbor2025!")
        print(f"Manager user: {manager_user.email} / Manager2025!")
        print(f"API key: {raw_key}")
        print(f"Employees: {len(employees_data)}")
        print(f"Integrations: {len(integrations_data)}")
        print(f"Calculation runs: 2")


if __name__ == "__main__":
    asyncio.run(seed())
