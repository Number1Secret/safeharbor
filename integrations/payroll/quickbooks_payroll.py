"""
QuickBooks Payroll Integration

Connects to Intuit QuickBooks Payroll API for employee data,
pay runs, and W-2 adjustments.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, PayrollData, PayrollIntegration

logger = logging.getLogger(__name__)

QB_API_BASE = "https://quickbooks.api.intuit.com"


class QuickBooksPayrollIntegration(PayrollIntegration):
    """QuickBooks Payroll integration."""

    provider_name = "quickbooks"
    base_url = QB_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.realm_id = (config or {}).get("realm_id", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_url}/v3/company/{self.realm_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
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
            response = await self.client.get("/companyinfo/" + self.realm_id)
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"QuickBooks connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                auth=(client_id, client_secret),
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
        start_position = 1
        max_results = 100

        while True:
            query = f"SELECT * FROM Employee STARTPOSITION {start_position} MAXRESULTS {max_results}"
            if since:
                query = f"SELECT * FROM Employee WHERE MetaData.LastUpdatedTime > '{since.isoformat()}' STARTPOSITION {start_position} MAXRESULTS {max_results}"

            response = await self.client.get(
                "/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            employees = data.get("QueryResponse", {}).get("Employee", [])

            if not employees:
                break

            for emp in employees:
                name = emp.get("DisplayName", "").split(" ", 1)
                first = emp.get("GivenName", name[0] if name else "")
                last = emp.get("FamilyName", name[1] if len(name) > 1 else "")

                yield EmployeeData(
                    external_id=str(emp.get("Id", "")),
                    first_name=first,
                    last_name=last,
                    email=emp.get("PrimaryEmailAddr", {}).get("Address"),
                    ssn_last_four=emp.get("SSN", "")[-4:] if emp.get("SSN") else None,
                    hire_date=_parse_date(emp.get("HiredDate")),
                    termination_date=_parse_date(emp.get("ReleasedDate")),
                    is_active=emp.get("Active", True),
                    job_title=emp.get("JobTitle"),
                    department=emp.get("Department", {}).get("name") if isinstance(emp.get("Department"), dict) else None,
                    hourly_rate=_to_decimal(emp.get("BillRate")),
                    is_hourly=emp.get("BillableTime", False),
                    raw_data=emp,
                )

            if len(employees) < max_results:
                break
            start_position += max_results

    async def fetch_payroll(
        self,
        period_start: date,
        period_end: date,
    ) -> AsyncGenerator[PayrollData, None]:
        # QB Payroll uses time activities and payroll items
        response = await self.client.get(
            "/query",
            params={
                "query": (
                    f"SELECT * FROM TimeActivity WHERE TxnDate >= '{period_start.isoformat()}' "
                    f"AND TxnDate <= '{period_end.isoformat()}'"
                ),
            },
        )
        response.raise_for_status()
        data = response.json()

        # Group time activities by employee
        employee_hours: dict[str, dict] = {}

        for activity in data.get("QueryResponse", {}).get("TimeActivity", []):
            emp_ref = activity.get("EmployeeRef", {})
            emp_id = str(emp_ref.get("value", ""))
            if not emp_id:
                continue

            if emp_id not in employee_hours:
                employee_hours[emp_id] = {
                    "regular": Decimal("0"),
                    "overtime": Decimal("0"),
                    "rate": None,
                    "raw_entries": [],
                }

            hours = _to_decimal(activity.get("Hours", 0))
            rate = activity.get("HourlyRate", {}).get("value")

            if activity.get("BillableStatus") == "HasBeenBilled":
                employee_hours[emp_id]["overtime"] += hours
            else:
                employee_hours[emp_id]["regular"] += hours

            if rate:
                employee_hours[emp_id]["rate"] = _to_decimal(rate)
            employee_hours[emp_id]["raw_entries"].append(activity)

        for emp_id, hours in employee_hours.items():
            yield PayrollData(
                external_id=f"{emp_id}_{period_start.isoformat()}",
                employee_external_id=emp_id,
                period_start=period_start,
                period_end=period_end,
                regular_hours=hours["regular"],
                overtime_hours=hours["overtime"],
                hourly_rate=hours.get("rate"),
                raw_data={"time_activities": hours["raw_entries"]},
            )

    async def write_w2_values(
        self,
        employee_external_id: str,
        box_12_values: dict[str, Decimal],
    ) -> bool:
        """Write W-2 Box 12 values via QuickBooks payroll adjustments."""
        try:
            for code, amount in box_12_values.items():
                response = await self.client.post(
                    "/journalentry",
                    json={
                        "DocNumber": f"SH-W2-{code}-{employee_external_id}",
                        "TxnDate": date.today().isoformat(),
                        "PrivateNote": f"SafeHarbor W-2 Box 12 Code {code}: ${amount}",
                        "Line": [
                            {
                                "Amount": float(amount),
                                "Description": f"OBBB W-2 Box 12 Code {code}",
                                "DetailType": "JournalEntryLineDetail",
                                "JournalEntryLineDetail": {
                                    "PostingType": "Debit",
                                    "Entity": {
                                        "Type": "Employee",
                                        "EntityRef": {"value": employee_external_id},
                                    },
                                },
                            }
                        ],
                    },
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"QB W-2 write failed for {employee_external_id}: {e}")
            return False


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        if isinstance(value, dict):
            value = value.get("value", "0")
        return Decimal(str(value))
    except Exception:
        return Decimal("0")
