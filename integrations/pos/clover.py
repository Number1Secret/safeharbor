"""
Clover POS Integration

Connects to Clover API for employee, shift, and tip data.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, POSIntegration, ShiftData, TipData

logger = logging.getLogger(__name__)

CLOVER_API_BASE = "https://api.clover.com/v3"


class CloverIntegration(POSIntegration):
    """Clover POS integration."""

    provider_name = "clover"
    base_url = CLOVER_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.merchant_id = (config or {}).get("merchant_id", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_url}/merchants/{self.merchant_id}",
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
            response = await self.client.get("")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Clover connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        # Clover uses long-lived tokens; re-authentication via OAuth
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                "https://sandbox.dev.clover.com/oauth/v2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": self.refresh_token,
                },
            )
            response.raise_for_status()
            data = response.json()

        return data.get("access_token", ""), None, None

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        offset = 0
        limit = 100

        while True:
            response = await self.client.get(
                "/employees",
                params={"offset": offset, "limit": limit, "expand": "roles"},
            )
            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])

            if not elements:
                break

            for emp in elements:
                yield EmployeeData(
                    external_id=emp.get("id", ""),
                    first_name=emp.get("name", "").split(" ")[0],
                    last_name=" ".join(emp.get("name", "").split(" ")[1:]),
                    email=emp.get("email"),
                    is_active=not emp.get("deletedTime"),
                    job_title=_get_role(emp),
                    raw_data=emp,
                )

            if len(elements) < limit:
                break
            offset += limit

    async def fetch_shifts(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

        offset = 0
        limit = 100

        while True:
            response = await self.client.get(
                "/shifts",
                params={
                    "filter": f"in_time>={start_ts}&in_time<={end_ts}",
                    "offset": offset,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])

            if not elements:
                break

            for shift in elements:
                clock_in = _from_epoch_ms(shift.get("inTime"))
                clock_out = _from_epoch_ms(shift.get("outTime"))

                hours = Decimal("0")
                ot_hours = Decimal("0")
                if clock_in and clock_out:
                    total_sec = (clock_out - clock_in).total_seconds()
                    total_hours = Decimal(str(total_sec / 3600))
                    if total_hours > Decimal("8"):
                        hours = Decimal("8")
                        ot_hours = total_hours - Decimal("8")
                    else:
                        hours = max(total_hours, Decimal("0"))

                yield ShiftData(
                    external_id=shift.get("id", ""),
                    employee_external_id=shift.get("employee", {}).get("id", ""),
                    shift_date=clock_in.date() if clock_in else start_date,
                    clock_in=clock_in or datetime.min,
                    clock_out=clock_out,
                    regular_hours=hours,
                    overtime_hours=ot_hours,
                    raw_data=shift,
                )

            if len(elements) < limit:
                break
            offset += limit

    async def fetch_tips(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[TipData, None]:
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

        tip_agg: dict[str, dict[str, TipData]] = {}
        offset = 0
        limit = 100

        while True:
            response = await self.client.get(
                "/payments",
                params={
                    "filter": f"createdTime>={start_ts}&createdTime<={end_ts}",
                    "offset": offset,
                    "limit": limit,
                    "expand": "employee",
                },
            )
            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])

            if not elements:
                break

            for payment in elements:
                tip_amount = payment.get("tipAmount", 0)
                if tip_amount <= 0:
                    continue

                emp_id = payment.get("employee", {}).get("id", "unknown")
                created = _from_epoch_ms(payment.get("createdTime"))
                if not created:
                    continue

                dk = created.date().isoformat()
                tip_decimal = Decimal(str(tip_amount)) / Decimal("100")

                if emp_id not in tip_agg:
                    tip_agg[emp_id] = {}
                if dk not in tip_agg[emp_id]:
                    tip_agg[emp_id][dk] = TipData(
                        external_id=f"{emp_id}_{dk}",
                        employee_external_id=emp_id,
                        shift_date=created.date(),
                        raw_data={},
                    )

                tender_type = payment.get("tender", {}).get("label", "")
                if "cash" in tender_type.lower():
                    tip_agg[emp_id][dk].cash_tips += tip_decimal
                else:
                    tip_agg[emp_id][dk].charged_tips += tip_decimal

            if len(elements) < limit:
                break
            offset += limit

        for emp_tips in tip_agg.values():
            for tip in emp_tips.values():
                yield tip


def _from_epoch_ms(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000)
    except (ValueError, TypeError, OSError):
        return None


def _get_role(emp: dict) -> str | None:
    roles = emp.get("roles", {}).get("elements", [])
    if roles:
        return roles[0].get("name")
    return None
