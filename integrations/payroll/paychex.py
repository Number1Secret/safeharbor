"""
Paychex Payroll Integration

Connects to Paychex API for employee roster, payroll data, and W-2 write-back.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, PayrollData, PayrollIntegration

logger = logging.getLogger(__name__)

PAYCHEX_API_BASE = "https://api.paychex.com"


class PaychexIntegration(PayrollIntegration):
    """Paychex payroll integration."""

    provider_name = "paychex"
    base_url = PAYCHEX_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.company_id = (config or {}).get("company_id", "")
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
            response = await self.client.get(
                f"/companies/{self.company_id}"
            )
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Paychex connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.base_url}/auth/oauth/v2/token",
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
        offset = 0
        limit = 50

        while True:
            response = await self.client.get(
                f"/companies/{self.company_id}/workers",
                params={"offset": offset, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            workers = data.get("content", [])

            if not workers:
                break

            for worker in workers:
                name = worker.get("name", {})
                employment = worker.get("currentEmployment", {})

                yield EmployeeData(
                    external_id=worker.get("workerId", ""),
                    first_name=name.get("givenName", ""),
                    last_name=name.get("familyName", ""),
                    email=_get_email(worker),
                    hire_date=_parse_date(employment.get("hireDate")),
                    termination_date=_parse_date(employment.get("terminationDate")),
                    is_active=worker.get("workerStatus") == "ACTIVE",
                    job_title=employment.get("jobTitle"),
                    department=employment.get("departmentName"),
                    hourly_rate=_to_decimal(
                        worker.get("currentPayRate", {}).get("rateAmount")
                    ),
                    is_hourly=worker.get("currentPayRate", {}).get("rateType") == "HOURLY",
                    raw_data=worker,
                )

            if len(workers) < limit:
                break
            offset += limit

    async def fetch_payroll(
        self,
        period_start: date,
        period_end: date,
    ) -> AsyncGenerator[PayrollData, None]:
        response = await self.client.get(
            f"/companies/{self.company_id}/checks",
            params={
                "payperiodstartdate": period_start.isoformat(),
                "payperiodenddate": period_end.isoformat(),
            },
        )
        response.raise_for_status()
        data = response.json()

        for check in data.get("content", []):
            worker_id = check.get("workerId", "")
            earnings = check.get("earnings", [])
            taxes = check.get("taxes", [])

            hours = _extract_hours(earnings)
            tax_amounts = _extract_taxes(taxes)

            yield PayrollData(
                external_id=check.get("checkId", ""),
                employee_external_id=worker_id,
                period_start=_parse_date(check.get("payPeriodStartDate")) or period_start,
                period_end=_parse_date(check.get("payPeriodEndDate")) or period_end,
                pay_date=_parse_date(check.get("checkDate")),
                regular_hours=hours["regular"],
                overtime_hours=hours["overtime"],
                double_time_hours=hours["double_time"],
                pto_hours=hours["pto"],
                gross_wages=_to_decimal(check.get("grossAmount")),
                net_wages=_to_decimal(check.get("netAmount")),
                hourly_rate=hours.get("rate"),
                tips_reported=hours.get("tips", Decimal("0")),
                bonuses=hours.get("bonus", Decimal("0")),
                federal_tax=tax_amounts.get("federal", Decimal("0")),
                state_tax=tax_amounts.get("state", Decimal("0")),
                social_security=tax_amounts.get("social_security", Decimal("0")),
                medicare=tax_amounts.get("medicare", Decimal("0")),
                raw_data=check,
            )

    async def write_w2_values(
        self,
        employee_external_id: str,
        box_12_values: dict[str, Decimal],
    ) -> bool:
        try:
            payload = {
                "w2Adjustments": [
                    {"boxCode": f"12{code}", "amount": str(amount)}
                    for code, amount in box_12_values.items()
                ]
            }
            response = await self.client.post(
                f"/companies/{self.company_id}/workers/{employee_external_id}/w2adjustments",
                json=payload,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Paychex W-2 write failed for {employee_external_id}: {e}")
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
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _get_email(worker: dict) -> str | None:
    communications = worker.get("communications", [])
    for comm in communications:
        if comm.get("type") == "EMAIL":
            return comm.get("value")
    return None


def _extract_hours(earnings: list) -> dict:
    hours = {
        "regular": Decimal("0"), "overtime": Decimal("0"),
        "double_time": Decimal("0"), "pto": Decimal("0"),
        "rate": None, "tips": Decimal("0"), "bonus": Decimal("0"),
    }

    for earning in earnings:
        code = earning.get("earningCode", "").upper()
        h = _to_decimal(earning.get("hours"))
        amount = _to_decimal(earning.get("amount"))

        if code in ("REG", "REGULAR"):
            hours["regular"] += h
            if earning.get("rate"):
                hours["rate"] = _to_decimal(earning["rate"])
        elif code in ("OT", "OVT", "OVERTIME"):
            hours["overtime"] += h
        elif code in ("DT", "DBL"):
            hours["double_time"] += h
        elif code in ("PTO", "VAC", "SICK", "HOL"):
            hours["pto"] += h
        elif code in ("TIP", "TIPS"):
            hours["tips"] += amount
        elif code in ("BON", "BONUS"):
            hours["bonus"] += amount

    return hours


def _extract_taxes(taxes: list) -> dict:
    result = {
        "federal": Decimal("0"), "state": Decimal("0"),
        "social_security": Decimal("0"), "medicare": Decimal("0"),
    }

    for tax in taxes:
        code = tax.get("taxCode", "").upper()
        amount = _to_decimal(tax.get("amount"))

        if "FIT" in code or "FEDERAL" in code:
            result["federal"] += amount
        elif "SIT" in code or "STATE" in code:
            result["state"] += amount
        elif "SS" in code or "OASDI" in code or "SOC" in code:
            result["social_security"] += amount
        elif "MED" in code:
            result["medicare"] += amount

    return result
