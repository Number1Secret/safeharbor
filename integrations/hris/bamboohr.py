"""
BambooHR Integration

Connects to BambooHR API for employee details and HR data.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, HRISIntegration

logger = logging.getLogger(__name__)


class BambooHRIntegration(HRISIntegration):
    """BambooHR HRIS integration."""

    provider_name = "bamboohr"
    base_url = ""  # Set dynamically from subdomain

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.subdomain = (config or {}).get("subdomain", "")
        self.base_url = f"https://api.bamboohr.com/api/gateway.php/{self.subdomain}/v1"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                auth=(self.access_token, "x"),  # API key as username
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> bool:
        try:
            response = await self.client.get("/employees/directory")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"BambooHR connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        # BambooHR uses API keys, not OAuth refresh
        # Return current token as-is
        return self.access_token, None, None

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        # Use directory for listing
        response = await self.client.get("/employees/directory")
        response.raise_for_status()
        data = response.json()

        for emp in data.get("employees", []):
            yield EmployeeData(
                external_id=str(emp.get("id", "")),
                first_name=emp.get("firstName", ""),
                last_name=emp.get("lastName", ""),
                email=emp.get("workEmail"),
                hire_date=_parse_date(emp.get("hireDate")),
                is_active=emp.get("status") == "Active",
                job_title=emp.get("jobTitle"),
                department=emp.get("department"),
                location=emp.get("location"),
                raw_data=emp,
            )

    async def fetch_employee_details(
        self,
        employee_external_id: str,
    ) -> EmployeeData | None:
        """Fetch detailed employee information from BambooHR."""
        fields = [
            "firstName", "lastName", "workEmail", "hireDate",
            "terminationDate", "status", "jobTitle", "department",
            "location", "payRate", "payType", "ssn",
            "dateOfBirth", "address1", "city", "state", "zipCode",
        ]

        response = await self.client.get(
            f"/employees/{employee_external_id}",
            params={"fields": ",".join(fields)},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        emp = response.json()

        ssn = emp.get("ssn", "")
        ssn_last_four = ssn[-4:] if ssn and len(ssn) >= 4 else None

        return EmployeeData(
            external_id=employee_external_id,
            first_name=emp.get("firstName", ""),
            last_name=emp.get("lastName", ""),
            email=emp.get("workEmail"),
            ssn_last_four=ssn_last_four,
            hire_date=_parse_date(emp.get("hireDate")),
            termination_date=_parse_date(emp.get("terminationDate")),
            is_active=emp.get("status") == "Active",
            job_title=emp.get("jobTitle"),
            department=emp.get("department"),
            hourly_rate=_to_decimal(emp.get("payRate")),
            is_hourly=emp.get("payType") == "Hourly",
            raw_data=emp,
        )

    async def fetch_time_off(
        self,
        employee_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Fetch time-off records for PTO tracking."""
        response = await self.client.get(
            "/time_off/requests",
            params={
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "employeeId": employee_id,
                "status": "approved",
            },
        )
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
