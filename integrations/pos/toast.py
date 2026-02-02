"""
Toast POS Integration

Connects to Toast API for shift logs, tip reports, and job code mapping.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import (
    EmployeeData,
    POSIntegration,
    ShiftData,
    SyncResult,
    TipData,
)

logger = logging.getLogger(__name__)

TOAST_API_BASE = "https://ws-api.toasttab.com"


class ToastIntegration(POSIntegration):
    """Toast POS integration for shift and tip data."""

    provider_name = "toast"
    base_url = TOAST_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.restaurant_guid = (config or {}).get("restaurant_guid", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Toast-Restaurant-External-ID": self.restaurant_guid,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> bool:
        """Verify Toast API connection."""
        try:
            response = await self.client.get("/restaurants/v1/restaurants")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Toast connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        """
        Refresh Toast OAuth tokens.

        Toast uses client credentials flow, so we re-authenticate
        rather than using a refresh token.
        """
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.base_url}/authentication/v1/authentication/login",
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "userAccessType": "TOAST_MACHINE_CLIENT",
                },
            )
            response.raise_for_status()
            data = response.json()

        new_token = data.get("token", {}).get("accessToken", "")
        expires_in = data.get("token", {}).get("expiresIn", 3600)

        return new_token, None, expires_in

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        """Fetch employee records from Toast."""
        offset = 0
        page_size = 100

        while True:
            params = {"pageSize": page_size, "page": offset}
            if since:
                params["modifiedDate"] = since.isoformat()

            response = await self.client.get(
                "/labor/v1/employees",
                params=params,
            )
            response.raise_for_status()
            employees = response.json()

            if not employees:
                break

            for emp in employees:
                yield EmployeeData(
                    external_id=emp.get("guid", ""),
                    first_name=emp.get("firstName", ""),
                    last_name=emp.get("lastName", ""),
                    email=emp.get("email"),
                    hire_date=_parse_date(emp.get("createdDate")),
                    termination_date=_parse_date(emp.get("deletedDate")),
                    is_active=not emp.get("deleted", False),
                    job_title=_extract_job_title(emp),
                    hourly_rate=_parse_decimal(emp.get("wageAmount")),
                    is_hourly=emp.get("wageType") == "HOURLY",
                    raw_data=emp,
                )

            if len(employees) < page_size:
                break
            offset += 1

    async def fetch_shifts(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        """
        Fetch shift/timecard data from Toast labor API.

        Args:
            start_date: Start of date range
            end_date: End of date range
        """
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }

        response = await self.client.get(
            "/labor/v1/timeEntries",
            params=params,
        )
        response.raise_for_status()
        entries = response.json()

        for entry in entries:
            clock_in = _parse_datetime(entry.get("inDate"))
            clock_out = _parse_datetime(entry.get("outDate"))

            if not clock_in:
                continue

            # Calculate hours
            regular_hours = Decimal("0")
            overtime_hours = Decimal("0")
            if clock_in and clock_out:
                total_seconds = (clock_out - clock_in).total_seconds()
                break_mins = entry.get("breakTime", 0)
                worked_seconds = total_seconds - (break_mins * 60)
                total_hours = Decimal(str(worked_seconds / 3600))

                if total_hours > Decimal("8"):
                    regular_hours = Decimal("8")
                    overtime_hours = total_hours - Decimal("8")
                else:
                    regular_hours = max(total_hours, Decimal("0"))

            yield ShiftData(
                external_id=entry.get("guid", ""),
                employee_external_id=entry.get("employeeReference", {}).get("guid", ""),
                shift_date=clock_in.date() if clock_in else start_date,
                clock_in=clock_in or datetime.min,
                clock_out=clock_out,
                break_minutes=entry.get("breakTime", 0),
                regular_hours=regular_hours,
                overtime_hours=overtime_hours,
                job_code=entry.get("jobReference", {}).get("guid"),
                job_title=entry.get("jobReference", {}).get("title"),
                hourly_rate=_parse_decimal(entry.get("regularHourlyWage")),
                raw_data=entry,
            )

    async def fetch_tips(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[TipData, None]:
        """
        Fetch tip data from Toast.

        Combines cash tips, charged tips, and tip pool distributions.
        """
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }

        # Fetch orders with tip data
        response = await self.client.get(
            "/orders/v2/ordersBulk",
            params=params,
        )
        response.raise_for_status()
        orders = response.json()

        # Aggregate tips by employee by day
        tip_aggregation: dict[str, dict[str, TipData]] = {}

        for order in orders:
            for check in order.get("checks", []):
                server_guid = check.get("appliedServiceChargeServerGuid", "")
                if not server_guid:
                    # Try to get from payments
                    payments = check.get("payments", [])
                    if payments:
                        server_guid = payments[0].get("refundServerGuid", "")

                if not server_guid:
                    continue

                order_date = _parse_datetime(order.get("closedDate"))
                if not order_date:
                    continue

                date_key = order_date.date().isoformat()
                emp_key = server_guid

                if emp_key not in tip_aggregation:
                    tip_aggregation[emp_key] = {}

                if date_key not in tip_aggregation[emp_key]:
                    tip_aggregation[emp_key][date_key] = TipData(
                        external_id=f"{emp_key}_{date_key}",
                        employee_external_id=emp_key,
                        shift_date=order_date.date(),
                        cash_tips=Decimal("0"),
                        charged_tips=Decimal("0"),
                        tip_pool_out=Decimal("0"),
                        tip_pool_in=Decimal("0"),
                        raw_data={},
                    )

                tip_record = tip_aggregation[emp_key][date_key]

                # Process payments for tip amounts
                for payment in check.get("payments", []):
                    tip_amount = _parse_decimal(payment.get("tipAmount"))
                    if tip_amount:
                        payment_type = payment.get("type", "")
                        if payment_type == "CASH":
                            tip_record.cash_tips += tip_amount
                        else:
                            tip_record.charged_tips += tip_amount

        # Fetch tip pool distributions
        try:
            pool_response = await self.client.get(
                "/labor/v1/tipDistributions",
                params=params,
            )
            if pool_response.status_code == 200:
                distributions = pool_response.json()
                for dist in distributions:
                    emp_guid = dist.get("employeeReference", {}).get("guid", "")
                    dist_date = _parse_date(dist.get("date"))
                    if emp_guid and dist_date:
                        date_key = dist_date.isoformat()
                        if emp_guid not in tip_aggregation:
                            tip_aggregation[emp_guid] = {}
                        if date_key not in tip_aggregation[emp_guid]:
                            tip_aggregation[emp_guid][date_key] = TipData(
                                external_id=f"{emp_guid}_{date_key}",
                                employee_external_id=emp_guid,
                                shift_date=dist_date,
                                cash_tips=Decimal("0"),
                                charged_tips=Decimal("0"),
                                raw_data={},
                            )
                        record = tip_aggregation[emp_guid][date_key]
                        amount = _parse_decimal(dist.get("amount"))
                        if amount:
                            if dist.get("type") == "CONTRIBUTION":
                                record.tip_pool_out += amount
                            else:
                                record.tip_pool_in += amount
        except httpx.HTTPError:
            logger.warning("Failed to fetch tip distributions, skipping pool data")

        # Yield all aggregated tip records
        for emp_tips in tip_aggregation.values():
            for tip_record in emp_tips.values():
                yield tip_record

    async def fetch_job_codes(self) -> list[dict]:
        """
        Fetch job codes/roles from Toast for TTOC mapping.

        Returns list of job definitions with titles and departments.
        """
        response = await self.client.get("/labor/v1/jobs")
        response.raise_for_status()
        jobs = response.json()

        return [
            {
                "external_id": job.get("guid", ""),
                "title": job.get("title", ""),
                "is_tipped": job.get("tippedWage", False),
                "department": job.get("departmentReference", {}).get("name"),
                "wage_amount": job.get("defaultWage"),
                "raw_data": job,
            }
            for job in jobs
        ]

    async def fetch_labor_summary(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        Fetch aggregated labor summary for a date range.

        Useful for reconciliation with payroll data.
        """
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }

        response = await self.client.get(
            "/labor/v1/laborSummary",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# Helper functions

def _parse_date(value: str | None) -> date | None:
    """Parse ISO date string."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _parse_datetime(value: str | int | None) -> datetime | None:
    """Parse Toast datetime (can be ISO string or epoch ms)."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, OSError):
        return None


def _parse_decimal(value) -> Decimal | None:
    """Parse numeric value to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _extract_job_title(employee: dict) -> str | None:
    """Extract primary job title from Toast employee."""
    jobs = employee.get("jobs", [])
    if jobs:
        return jobs[0].get("title")
    return employee.get("jobTitle")
