"""
Square POS Integration

Connects to Square API for employee data, shift logs, and tip reports.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import httpx

from integrations.base import EmployeeData, POSIntegration, ShiftData, TipData

logger = logging.getLogger(__name__)

SQUARE_API_BASE = "https://connect.squareup.com/v2"


class SquareIntegration(POSIntegration):
    """Square POS integration."""

    provider_name = "square"
    base_url = SQUARE_API_BASE

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(access_token, refresh_token, config)
        self.location_id = (config or {}).get("location_id", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Square-Version": "2024-01-18",
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
            response = await self.client.get("/merchants/me")
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Square connection test failed: {e}")
            return False

    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        async with httpx.AsyncClient() as http:
            response = await http.post(
                "https://connect.squareup.com/oauth2/token",
                json={
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
            data.get("expires_at"),
        )

    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        cursor = None
        while True:
            body: dict = {"limit": 100}
            if cursor:
                body["cursor"] = cursor
            if self.location_id:
                body["location_ids"] = [self.location_id]

            response = await self.client.post("/team-members/search", json=body)
            response.raise_for_status()
            data = response.json()

            for member in data.get("team_members", []):
                yield EmployeeData(
                    external_id=member.get("id", ""),
                    first_name=member.get("given_name", ""),
                    last_name=member.get("family_name", ""),
                    email=member.get("email_address"),
                    is_active=member.get("status") == "ACTIVE",
                    job_title=_get_job_title(member),
                    raw_data=member,
                )

            cursor = data.get("cursor")
            if not cursor:
                break

    async def fetch_shifts(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        cursor = None
        while True:
            body = {
                "query": {
                    "filter": {
                        "start": {
                            "start_at": f"{start_date.isoformat()}T00:00:00Z",
                            "end_at": f"{end_date.isoformat()}T23:59:59Z",
                        },
                    },
                },
                "limit": 200,
            }
            if self.location_id:
                body["query"]["filter"]["location_ids"] = [self.location_id]
            if cursor:
                body["cursor"] = cursor

            response = await self.client.post("/labor/shifts/search", json=body)
            response.raise_for_status()
            data = response.json()

            for shift in data.get("shifts", []):
                clock_in = _parse_datetime(shift.get("start_at"))
                clock_out = _parse_datetime(shift.get("end_at"))

                regular_hours = Decimal("0")
                overtime_hours = Decimal("0")
                if clock_in and clock_out:
                    breaks = sum(
                        b.get("break_duration_minutes", 0)
                        for b in shift.get("breaks", [])
                    )
                    total = (clock_out - clock_in).total_seconds() / 3600
                    worked = Decimal(str(total)) - Decimal(str(breaks / 60))
                    if worked > Decimal("8"):
                        regular_hours = Decimal("8")
                        overtime_hours = worked - Decimal("8")
                    else:
                        regular_hours = max(worked, Decimal("0"))

                yield ShiftData(
                    external_id=shift.get("id", ""),
                    employee_external_id=shift.get("team_member_id", ""),
                    shift_date=clock_in.date() if clock_in else start_date,
                    clock_in=clock_in or datetime.min,
                    clock_out=clock_out,
                    break_minutes=sum(
                        b.get("break_duration_minutes", 0)
                        for b in shift.get("breaks", [])
                    ),
                    regular_hours=regular_hours,
                    overtime_hours=overtime_hours,
                    job_title=shift.get("wage", {}).get("title"),
                    hourly_rate=_to_decimal(
                        shift.get("wage", {}).get("hourly_rate", {}).get("amount")
                    ),
                    location=self.location_id,
                    raw_data=shift,
                )

            cursor = data.get("cursor")
            if not cursor:
                break

    async def fetch_tips(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[TipData, None]:
        # Square tip data comes from payments/orders
        cursor = None
        tip_agg: dict[str, dict[str, TipData]] = {}

        while True:
            body = {
                "query": {
                    "filter": {
                        "date_time_filter": {
                            "closed_at": {
                                "start_at": f"{start_date.isoformat()}T00:00:00Z",
                                "end_at": f"{end_date.isoformat()}T23:59:59Z",
                            }
                        }
                    },
                    "sort": {"sort_field": "CLOSED_AT", "sort_order": "ASC"},
                },
                "limit": 100,
            }
            if self.location_id:
                body["query"]["filter"]["location_ids"] = [self.location_id]
            if cursor:
                body["cursor"] = cursor

            response = await self.client.post("/orders/search", json=body)
            response.raise_for_status()
            data = response.json()

            for order in data.get("orders", []):
                for tender in order.get("tenders", []):
                    tip_money = tender.get("tip_money", {})
                    tip_amount = _money_to_decimal(tip_money)
                    if tip_amount <= Decimal("0"):
                        continue

                    emp_id = tender.get("employee_id", "unknown")
                    order_date = _parse_datetime(order.get("closed_at"))
                    if not order_date:
                        continue
                    dk = order_date.date().isoformat()

                    if emp_id not in tip_agg:
                        tip_agg[emp_id] = {}
                    if dk not in tip_agg[emp_id]:
                        tip_agg[emp_id][dk] = TipData(
                            external_id=f"{emp_id}_{dk}",
                            employee_external_id=emp_id,
                            shift_date=order_date.date(),
                            raw_data={},
                        )

                    payment_type = tender.get("type", "")
                    if payment_type == "CASH":
                        tip_agg[emp_id][dk].cash_tips += tip_amount
                    else:
                        tip_agg[emp_id][dk].charged_tips += tip_amount

            cursor = data.get("cursor")
            if not cursor:
                break

        for emp_tips in tip_agg.values():
            for tip in emp_tips.values():
                yield tip


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money_to_decimal(money: dict) -> Decimal:
    """Convert Square Money object (amount in cents) to Decimal dollars."""
    amount = money.get("amount", 0)
    return Decimal(str(amount)) / Decimal("100")


def _get_job_title(member: dict) -> str | None:
    assignments = member.get("assigned_locations", {}).get("assignment_type")
    if assignments:
        return assignments
    return None
