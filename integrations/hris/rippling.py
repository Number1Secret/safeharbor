"""
Rippling HRIS Integration

Connects to Rippling API for employee and payroll data.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, HRISIntegration

logger = logging.getLogger(__name__)

RIPPLING_API_BASE = "https://api.rippling.com"


class RipplingIntegration(HRISIntegration):
    """Rippling HRIS integration."""

    provider_name = "rippling"
    base_url = RIPPLING_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> bool:
        try:
            response = await self.client.get("/platform/api/company")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Rippling connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.base_url}/platform/api/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        return (
            data["access_token"],
            data.get("refresh_token"),
            data.get("expires_in", 3600),
        )

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        cursor = None

        while True:
            params: dict = {"limit": 100}
            if cursor:
                params["cursor"] = cursor

            response = await self.client.get(
                "/platform/api/employees",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            employees = data.get("data", [])

            if not employees:
                break

            for emp in employees:
                yield EmployeeData(
                    external_id=emp.get("id", ""),
                    first_name=emp.get("firstName", ""),
                    last_name=emp.get("lastName", ""),
                    email=emp.get("workEmail"),
                    ssn_last_four=emp.get("ssnLast4"),
                    hire_date=_parse_date(emp.get("startDate")),
                    termination_date=_parse_date(emp.get("endDate")),
                    is_active=emp.get("employmentStatus") == "ACTIVE",
                    job_title=emp.get("title"),
                    department=emp.get("department", {}).get("name")
                    if isinstance(emp.get("department"), dict) else None,
                    hourly_rate=_to_decimal(emp.get("compensationRate")),
                    is_hourly=emp.get("flsaStatus") == "NON_EXEMPT",
                    raw_data=emp,
                )

            cursor = data.get("nextCursor")
            if not cursor:
                break

    async def fetch_employee_details(
        self,
        employee_external_id: str,
    ) -> EmployeeData | None:
        """Fetch detailed employee information from Rippling."""
        response = await self.client.get(
            f"/platform/api/employees/{employee_external_id}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        emp = response.json()

        return EmployeeData(
            external_id=emp.get("id", ""),
            first_name=emp.get("firstName", ""),
            last_name=emp.get("lastName", ""),
            email=emp.get("workEmail"),
            ssn_last_four=emp.get("ssnLast4"),
            hire_date=_parse_date(emp.get("startDate")),
            termination_date=_parse_date(emp.get("endDate")),
            is_active=emp.get("employmentStatus") == "ACTIVE",
            job_title=emp.get("title"),
            department=emp.get("department", {}).get("name")
            if isinstance(emp.get("department"), dict) else None,
            hourly_rate=_to_decimal(emp.get("compensationRate")),
            is_hourly=emp.get("flsaStatus") == "NON_EXEMPT",
            raw_data=emp,
        )

    async def fetch_compensation(
        self,
        employee_id: str,
    ) -> dict | None:
        """Fetch compensation details for an employee."""
        response = await self.client.get(
            f"/platform/api/employees/{employee_id}/compensation",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _to_decimal(value) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
