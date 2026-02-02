"""
ADP Payroll Integration

Connects to ADP Workforce Now API for employee roster,
pay rates, payroll data, and W-2 write-back.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, PayrollData, PayrollIntegration

logger = logging.getLogger(__name__)

ADP_API_BASE = "https://api.adp.com"


class ADPIntegration(PayrollIntegration):
    """ADP Workforce Now payroll integration."""

    provider_name = "adp"
    base_url = ADP_API_BASE

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
            response = await self.client.get("/hr/v2/workers?$top=1")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"ADP connection test failed: {e}")
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
        skip = 0
        page_size = 100

        while True:
            params = {"$top": page_size, "$skip": skip}
            if since:
                params["$filter"] = f"workerStatus/statusCode/codeValue ne 'Terminated' or workers/workerDates/terminationDate ge '{since.date().isoformat()}'"

            response = await self.client.get("/hr/v2/workers", params=params)
            response.raise_for_status()
            data = response.json()
            workers = data.get("workers", [])

            if not workers:
                break

            for worker in workers:
                person = worker.get("person", {})
                name = person.get("legalName", {})
                status = worker.get("workerStatus", {})

                # Get primary work assignment
                assignments = worker.get("workAssignments", [])
                primary = assignments[0] if assignments else {}

                yield EmployeeData(
                    external_id=worker.get("associateOID", ""),
                    first_name=name.get("givenName", ""),
                    last_name=name.get("familyName1", ""),
                    email=_get_email(person),
                    ssn_last_four=_get_ssn_last_four(person),
                    hire_date=_parse_date(
                        worker.get("workerDates", {}).get("originalHireDate")
                    ),
                    termination_date=_parse_date(
                        worker.get("workerDates", {}).get("terminationDate")
                    ),
                    is_active=status.get("statusCode", {}).get("codeValue") == "Active",
                    job_title=primary.get("jobTitle"),
                    department=_get_department(primary),
                    hourly_rate=_get_hourly_rate(primary),
                    is_hourly=primary.get("payrollGroupCode") == "H",
                    raw_data=worker,
                )

            if len(workers) < page_size:
                break
            skip += page_size

    async def fetch_payroll(
        self,
        period_start: date,
        period_end: date,
    ) -> AsyncGenerator[PayrollData, None]:
        params = {
            "payPeriod.startDate": period_start.isoformat(),
            "payPeriod.endDate": period_end.isoformat(),
        }

        response = await self.client.get(
            "/payroll/v1/payroll-output",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        for payroll in data.get("payrollOutputs", []):
            for earning in payroll.get("associatePayrollOutputs", []):
                worker_id = earning.get("associateOID", "")
                pay_summary = earning.get("paySummary", {})
                deductions = earning.get("deductions", [])

                # Parse hours
                hours = _parse_hours(earning)

                yield PayrollData(
                    external_id=f"{worker_id}_{period_start.isoformat()}",
                    employee_external_id=worker_id,
                    period_start=period_start,
                    period_end=period_end,
                    pay_date=_parse_date(payroll.get("payDate")),
                    regular_hours=hours.get("regular", Decimal("0")),
                    overtime_hours=hours.get("overtime", Decimal("0")),
                    double_time_hours=hours.get("double_time", Decimal("0")),
                    pto_hours=hours.get("pto", Decimal("0")),
                    gross_wages=_to_decimal(pay_summary.get("grossPayAmount")),
                    net_wages=_to_decimal(pay_summary.get("netPayAmount")),
                    hourly_rate=_to_decimal(hours.get("rate")),
                    overtime_rate=_to_decimal(hours.get("ot_rate")),
                    tips_reported=_to_decimal(
                        pay_summary.get("tipsAmount", "0")
                    ),
                    bonuses=_sum_earning_category(earning, "Bonus"),
                    commissions=_sum_earning_category(earning, "Commission"),
                    federal_tax=_sum_deduction(deductions, "Federal"),
                    state_tax=_sum_deduction(deductions, "State"),
                    social_security=_sum_deduction(deductions, "Social Security"),
                    medicare=_sum_deduction(deductions, "Medicare"),
                    raw_data=earning,
                )

    async def write_w2_values(
        self,
        employee_external_id: str,
        box_12_values: dict[str, Decimal],
    ) -> bool:
        """Write W-2 Box 12 values to ADP."""
        payload = {
            "events": [
                {
                    "eventNameCode": {"codeValue": "worker.taxDocument.update"},
                    "data": {
                        "transform": {
                            "worker": {
                                "associateOID": employee_external_id,
                                "taxDocuments": [
                                    {
                                        "formType": "W-2",
                                        "box12Entries": [
                                            {
                                                "codeValue": code,
                                                "amount": str(amount),
                                            }
                                            for code, amount in box_12_values.items()
                                        ],
                                    }
                                ],
                            }
                        }
                    },
                }
            ]
        }

        try:
            response = await self.client.post(
                "/events/payroll/v1/worker-tax-document.update",
                json=payload,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"ADP W-2 write failed for {employee_external_id}: {e}")
            return False


# Helper functions

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _get_email(person: dict) -> str | None:
    contacts = person.get("communication", {}).get("emails", [])
    for contact in contacts:
        if contact.get("nameCode", {}).get("codeValue") == "Work":
            return contact.get("emailUri")
    return contacts[0].get("emailUri") if contacts else None


def _get_ssn_last_four(person: dict) -> str | None:
    ssn = person.get("governmentIDs", [{}])[0].get("idValue")
    if ssn and len(ssn) >= 4:
        return ssn[-4:]
    return None


def _get_department(assignment: dict) -> str | None:
    dept = assignment.get("homeOrganizationalUnits", [])
    for unit in dept:
        if unit.get("typeCode", {}).get("codeValue") == "Department":
            return unit.get("nameCode", {}).get("shortName")
    return None


def _get_hourly_rate(assignment: dict) -> Decimal | None:
    rate = assignment.get("baseRemuneration", {}).get("hourlyRateAmount")
    return _to_decimal(rate)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        if isinstance(value, dict):
            value = value.get("amountValue", "0")
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _parse_hours(earning: dict) -> dict:
    hours = {"regular": Decimal("0"), "overtime": Decimal("0"),
             "double_time": Decimal("0"), "pto": Decimal("0"),
             "rate": None, "ot_rate": None}
    for entry in earning.get("earnings", []):
        code = entry.get("earningCodeReference", {}).get("codeValue", "")
        amount = _to_decimal(entry.get("numberOfHours"))
        rate = entry.get("rate", {}).get("rateAmount")

        if code in ("REG", "Regular"):
            hours["regular"] += amount
            if rate:
                hours["rate"] = _to_decimal(rate)
        elif code in ("OT", "Overtime"):
            hours["overtime"] += amount
            if rate:
                hours["ot_rate"] = _to_decimal(rate)
        elif code in ("DT", "DoubleTime"):
            hours["double_time"] += amount
        elif code in ("PTO", "VAC", "SICK"):
            hours["pto"] += amount

    return hours


def _sum_earning_category(earning: dict, category: str) -> Decimal:
    total = Decimal("0")
    for entry in earning.get("earnings", []):
        if category.lower() in entry.get("earningCodeReference", {}).get("codeValue", "").lower():
            total += _to_decimal(entry.get("earningAmount"))
    return total


def _sum_deduction(deductions: list, category: str) -> Decimal:
    total = Decimal("0")
    for ded in deductions:
        if category.lower() in ded.get("deductionCodeReference", {}).get("shortName", "").lower():
            total += _to_decimal(ded.get("deductionAmount"))
    return total
