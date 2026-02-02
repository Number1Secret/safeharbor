"""
Base Integration Classes

Abstract base classes and common data models for all integrations.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import AsyncGenerator

from pydantic import BaseModel, Field


class IntegrationCategory(str, Enum):
    """Categories of integrations."""

    PAYROLL = "payroll"
    POS = "pos"
    TIMEKEEPING = "timekeeping"
    HRIS = "hris"


class EmployeeData(BaseModel):
    """Normalized employee data from any provider."""

    external_id: str = Field(..., description="ID in external system")
    first_name: str
    last_name: str
    email: str | None = None
    ssn_last_four: str | None = Field(None, description="Last 4 of SSN for matching")

    # Employment
    hire_date: date | None = None
    termination_date: date | None = None
    is_active: bool = True
    job_title: str | None = None
    department: str | None = None

    # Pay information
    hourly_rate: Decimal | None = None
    is_hourly: bool = True

    # Raw data from provider
    raw_data: dict = Field(default_factory=dict)


class PayrollData(BaseModel):
    """Normalized payroll data from any provider."""

    external_id: str = Field(..., description="Payroll record ID")
    employee_external_id: str = Field(..., description="Employee ID in external system")

    # Period
    period_start: date
    period_end: date
    pay_date: date | None = None

    # Hours
    regular_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    double_time_hours: Decimal = Decimal("0")
    pto_hours: Decimal = Decimal("0")

    # Wages
    gross_wages: Decimal = Decimal("0")
    net_wages: Decimal | None = None

    # Rates
    hourly_rate: Decimal | None = None
    overtime_rate: Decimal | None = None

    # Additional compensation
    tips_reported: Decimal = Decimal("0")
    bonuses: Decimal = Decimal("0")
    commissions: Decimal = Decimal("0")
    reimbursements: Decimal = Decimal("0")

    # Deductions
    federal_tax: Decimal = Decimal("0")
    state_tax: Decimal = Decimal("0")
    social_security: Decimal = Decimal("0")
    medicare: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")

    # Raw data
    raw_data: dict = Field(default_factory=dict)


class ShiftData(BaseModel):
    """Normalized shift/timecard data from timekeeping or POS."""

    external_id: str
    employee_external_id: str

    # Timing
    shift_date: date
    clock_in: datetime
    clock_out: datetime | None = None
    break_minutes: int = 0

    # Hours calculated
    regular_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")

    # Job info
    job_code: str | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None

    # Rate
    hourly_rate: Decimal | None = None

    # Raw data
    raw_data: dict = Field(default_factory=dict)


class TipData(BaseModel):
    """Normalized tip data from POS systems."""

    external_id: str
    employee_external_id: str

    # Date
    shift_date: date

    # Tip amounts
    cash_tips: Decimal = Decimal("0")
    charged_tips: Decimal = Decimal("0")
    tip_pool_out: Decimal = Decimal("0")  # Contributed to pool
    tip_pool_in: Decimal = Decimal("0")  # Received from pool

    @property
    def total_tips(self) -> Decimal:
        """Calculate total tips."""
        return self.cash_tips + self.charged_tips + self.tip_pool_in - self.tip_pool_out

    # Associated shift
    shift_id: str | None = None

    # Raw data
    raw_data: dict = Field(default_factory=dict)


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    sync_cursor: dict = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None


class BaseIntegration(ABC):
    """Abstract base class for all external integrations."""

    provider_name: str
    category: IntegrationCategory
    base_url: str

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        config: dict | None = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.config = config or {}

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify the integration connection is valid."""
        pass

    @abstractmethod
    async def refresh_access_token(self) -> tuple[str, str | None, int | None]:
        """
        Refresh OAuth tokens.

        Returns:
            Tuple of (new_access_token, new_refresh_token, expires_in_seconds)
        """
        pass

    @abstractmethod
    async def fetch_employees(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[EmployeeData, None]:
        """
        Fetch employee records.

        Args:
            since: Only fetch records updated since this timestamp

        Yields:
            EmployeeData objects
        """
        pass

    async def sync_employees(
        self,
        since: datetime | None = None,
    ) -> SyncResult:
        """
        Sync all employees from the provider.

        Returns:
            SyncResult with statistics
        """
        result = SyncResult(
            success=True,
            started_at=datetime.utcnow(),
        )

        try:
            async for employee in self.fetch_employees(since):
                result.records_fetched += 1
                # Actual storage would happen here
                result.records_created += 1
        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        result.completed_at = datetime.utcnow()
        return result


class PayrollIntegration(BaseIntegration):
    """Extended base for payroll systems."""

    category = IntegrationCategory.PAYROLL

    @abstractmethod
    async def fetch_payroll(
        self,
        period_start: date,
        period_end: date,
    ) -> AsyncGenerator[PayrollData, None]:
        """
        Fetch payroll data for a specific period.

        Args:
            period_start: Start of pay period
            period_end: End of pay period

        Yields:
            PayrollData objects
        """
        pass

    @abstractmethod
    async def write_w2_values(
        self,
        employee_external_id: str,
        box_12_values: dict[str, Decimal],
    ) -> bool:
        """
        Write calculated values to W-2 Box 12.

        Args:
            employee_external_id: Employee ID in payroll system
            box_12_values: Dict of box codes to values (e.g., {"TT": 1234.56})

        Returns:
            True if successful
        """
        pass


class POSIntegration(BaseIntegration):
    """Extended base for POS systems with tip data."""

    category = IntegrationCategory.POS

    @abstractmethod
    async def fetch_shifts(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        """Fetch shift data for date range."""
        pass

    @abstractmethod
    async def fetch_tips(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[TipData, None]:
        """Fetch tip data for date range."""
        pass


class TimekeepingIntegration(BaseIntegration):
    """Extended base for timekeeping systems."""

    category = IntegrationCategory.TIMEKEEPING

    @abstractmethod
    async def fetch_timecards(
        self,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[ShiftData, None]:
        """Fetch timecard/shift data for date range."""
        pass


class HRISIntegration(BaseIntegration):
    """Extended base for HRIS systems."""

    category = IntegrationCategory.HRIS

    @abstractmethod
    async def fetch_employee_details(
        self,
        employee_external_id: str,
    ) -> EmployeeData | None:
        """Fetch detailed employee information."""
        pass
