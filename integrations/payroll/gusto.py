"""
Gusto Payroll Integration

Connects to Gusto Partner API for employee data, payroll records,
and W-2 adjustments.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, PayrollData, PayrollIntegration

logger = logging.getLogger(__name__)

GUSTO_API_BASE = "https://api.gusto.com"


class GustoIntegration(PayrollIntegration):
    """Gusto payroll integration."""

    provider_name = "gusto"
    base_url = GUSTO_API_BASE

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
                    "X-Gusto-API-Version": "2024-03-01",
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
                f"/v1/companies/{self.company_id}"
            )
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Gusto connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.base_url}/oauth/token",
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
            data.get("expires_in", 7200),
        )

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        page = 1
        per_page = 100

        while True:
            response = await self.client.get(
                f"/v1/companies/{self.company_id}/employees",
                params={"page": page, "per": per_page},
            )
            response.raise_for_status()
            employees = response.json()

            if not employees:
                break

            for emp in employees:
                if since and emp.get("updated_at"):
                    updated = datetime.fromisoformat(emp["updated_at"].replace("Z", "+00:00"))
                    if updated < since:
                        continue

                jobs = emp.get("jobs", [])
                primary_job = jobs[0] if jobs else {}
                compensations = primary_job.get("compensations", [])
                current_comp = compensations[0] if compensations else {}

                yield EmployeeData(
                    external_id=str(emp.get("id", "")),
                    first_name=emp.get("first_name", ""),
                    last_name=emp.get("last_name", ""),
                    email=emp.get("email"),
                    ssn_last_four=emp.get("ssn", "")[-4:] if emp.get("ssn") else None,
                    hire_date=_parse_date(emp.get("date_of_birth")),
                    termination_date=_parse_date(
                        emp.get("terminations", [{}])[0].get("effective_date")
                        if emp.get("terminations") else None
                    ),
                    is_active=not emp.get("terminated", False),
                    job_title=primary_job.get("title"),
                    department=emp.get("department"),
                    hourly_rate=_to_decimal(current_comp.get("rate")),
                    is_hourly=current_comp.get("payment_unit") == "Hour",
                    raw_data=emp,
                )

            if len(employees) < per_page:
                break
            page += 1

    async def fetch_payroll(
        self,
        period_start: date,
        period_end: date,
    ) -> AsyncGenerator[PayrollData, None]:
        # Gusto uses payroll IDs; fetch payrolls for the period
        response = await self.client.get(
            f"/v1/companies/{self.company_id}/payrolls",
            params={
                "start_date": period_start.isoformat(),
                "end_date": period_end.isoformat(),
                "processed": "true",
            },
        )
        response.raise_for_status()
        payrolls = response.json()

        for payroll in payrolls:
            pay_period = payroll.get("pay_period", {})
            p_start = _parse_date(pay_period.get("start_date")) or period_start
            p_end = _parse_date(pay_period.get("end_date")) or period_end
            pay_date = _parse_date(payroll.get("check_date"))

            for emp_comp in payroll.get("employee_compensations", []):
                emp_id = str(emp_comp.get("employee_id", ""))

                # Parse fixed and hourly compensations
                hours = _extract_hours(emp_comp)
                taxes = _extract_taxes(emp_comp)

                gross = _to_decimal(emp_comp.get("gross_pay"))
                net = _to_decimal(emp_comp.get("net_pay"))

                yield PayrollData(
                    external_id=f"{emp_id}_{p_start.isoformat()}",
                    employee_external_id=emp_id,
                    period_start=p_start,
                    period_end=p_end,
                    pay_date=pay_date,
                    regular_hours=hours["regular"],
                    overtime_hours=hours["overtime"],
                    double_time_hours=hours["double_time"],
                    pto_hours=hours["pto"],
                    gross_wages=gross,
                    net_wages=net,
                    hourly_rate=hours.get("rate"),
                    overtime_rate=hours.get("ot_rate"),
                    tips_reported=hours.get("tips", Decimal("0")),
                    bonuses=hours.get("bonus", Decimal("0")),
                    federal_tax=taxes.get("federal", Decimal("0")),
                    state_tax=taxes.get("state", Decimal("0")),
                    social_security=taxes.get("social_security", Decimal("0")),
                    medicare=taxes.get("medicare", Decimal("0")),
                    raw_data=emp_comp,
                )

    async def write_w2_values(
        self,
        employee_external_id: str,
        box_12_values: dict[str, Decimal],
    ) -> bool:
        """Write W-2 Box 12 values via Gusto custom earnings."""
        try:
            for code, amount in box_12_values.items():
                response = await self.client.post(
                    f"/v1/companies/{self.company_id}/employees/{employee_external_id}/ytd_benefit_amounts_from_different_company",
                    json={
                        "benefit_type": f"W2_Box12_{code}",
                        "ytd_employee_deduction_amount": "0",
                        "ytd_company_contribution_amount": str(amount),
                    },
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Gusto W-2 write failed for {employee_external_id}: {e}")
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


def _extract_hours(emp_comp: dict) -> dict:
    hours = {
        "regular": Decimal("0"), "overtime": Decimal("0"),
        "double_time": Decimal("0"), "pto": Decimal("0"),
        "rate": None, "ot_rate": None, "tips": Decimal("0"),
        "bonus": Decimal("0"),
    }

    for comp in emp_comp.get("hourly_compensations", []):
        name = comp.get("name", "").lower()
        h = _to_decimal(comp.get("hours"))
        rate = comp.get("compensation_multiplier", 1)

        if "overtime" in name or rate == 1.5:
            hours["overtime"] += h
            if comp.get("rate"):
                hours["ot_rate"] = _to_decimal(comp["rate"])
        elif "double" in name or rate == 2:
            hours["double_time"] += h
        elif "pto" in name or "vacation" in name or "sick" in name:
            hours["pto"] += h
        else:
            hours["regular"] += h
            if comp.get("rate"):
                hours["rate"] = _to_decimal(comp["rate"])

    for comp in emp_comp.get("fixed_compensations", []):
        name = comp.get("name", "").lower()
        amount = _to_decimal(comp.get("amount"))
        if "tip" in name:
            hours["tips"] += amount
        elif "bonus" in name:
            hours["bonus"] += amount

    return hours


def _extract_taxes(emp_comp: dict) -> dict:
    taxes = {
        "federal": Decimal("0"), "state": Decimal("0"),
        "social_security": Decimal("0"), "medicare": Decimal("0"),
    }

    for tax in emp_comp.get("taxes", []):
        name = tax.get("name", "").lower()
        amount = _to_decimal(tax.get("amount"))

        if "federal income" in name or "fit" in name:
            taxes["federal"] += amount
        elif "state" in name or "sit" in name:
            taxes["state"] += amount
        elif "social security" in name or "oasdi" in name:
            taxes["social_security"] += amount
        elif "medicare" in name:
            taxes["medicare"] += amount

    return taxes
