"""
Deputy Timekeeping Integration

Connects to Deputy API for timesheet and shift data.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, ShiftData, TimekeepingIntegration

logger = logging.getLogger(__name__)

DEPUTY_API_BASE = "https://once.deputy.com/my"


class DeputyIntegration(TimekeepingIntegration):
    """Deputy timekeeping integration."""

    provider_name = "deputy"
    base_url = DEPUTY_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.subdomain = (config or {}).get("subdomain", "once")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            base = f"https://{self.subdomain}.deputy.com/api/v1"
            self._client = httpx.AsyncClient(
                base_url=base,
                headers={
                    "Authorization": f"OAuth {self.access_token}",
                    "Content-Type": "application/json",
                    "dp-meta-option": "none",
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
            response = await self.client.get("/me")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Deputy connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"https://{self.subdomain}.deputy.com/oauth/access_token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "longlife_refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()

        return (
            data["access_token"],
            data.get("refresh_token"),
            data.get("expires_in", 86400),
        )

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        start = 0
        max_records = 100

        while True:
            search = {
                "search": {
                    "s1": {"field": "Active", "type": "eq", "data": True},
                },
                "start": start,
                "max": max_records,
            }
            if since:
                search["search"]["s2"] = {
                    "field": "Modified",
                    "type": "ge",
                    "data": int(since.timestamp()),
                }

            response = await self.client.post(
                "/resource/Employee/QUERY",
                json=search,
            )
            response.raise_for_status()
            employees = response.json()

            if not employees:
                break

            for emp in employees:
                yield EmployeeData(
                    external_id=str(emp.get("Id", "")),
                    first_name=emp.get("FirstName", ""),
                    last_name=emp.get("LastName", ""),
                    email=emp.get("Email"),
                    hire_date=_parse_deputy_date(emp.get("StartDate")),
                    termination_date=_parse_deputy_date(emp.get("TerminationDate")),
                    is_active=emp.get("Active", True),
                    job_title=emp.get("Position"),
                    department=emp.get("Department"),
                    hourly_rate=_to_decimal(emp.get("PayRate")),
                    raw_data=emp,
                )

            if len(employees) < max_records:
                break
            start += max_records

    async def fetch_timecards(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

        search = {
            "search": {
                "s1": {"field": "StartTime", "type": "ge", "data": start_ts},
                "s2": {"field": "StartTime", "type": "le", "data": end_ts},
            },
            "max": 500,
        }

        response = await self.client.post(
            "/resource/Timesheet/QUERY",
            json=search,
        )
        response.raise_for_status()
        timesheets = response.json()

        for ts in timesheets:
            clock_in = _from_epoch(ts.get("StartTime"))
            clock_out = _from_epoch(ts.get("EndTime"))

            total_hours = _to_decimal(ts.get("TotalTime", 0)) / Decimal("3600")
            regular = min(total_hours, Decimal("8"))
            overtime = max(total_hours - Decimal("8"), Decimal("0"))

            yield ShiftData(
                external_id=str(ts.get("Id", "")),
                employee_external_id=str(ts.get("Employee", "")),
                shift_date=clock_in.date() if clock_in else start_date,
                clock_in=clock_in or datetime.min,
                clock_out=clock_out,
                break_minutes=int(_to_decimal(ts.get("BreakTime", 0)) / Decimal("60")),
                regular_hours=regular,
                overtime_hours=overtime,
                department=str(ts.get("OperationalUnit", "")),
                hourly_rate=_to_decimal(ts.get("Cost")),
                raw_data=ts,
            )


def _parse_deputy_date(value) -> date | None:
    if not value:
        return None
    try:
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).date()
    except (ValueError, TypeError, OSError):
        pass
    return None


def _from_epoch(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value))
    except (ValueError, TypeError, OSError):
        return None


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")
