"""
Write-Back Engine

Pushes calculated OBBB values back to payroll systems as W-2 Box 12 codes.

Box 12 Codes:
- TT: Qualified overtime + tips combined
- TP: Qualified tips only
- TS: Qualified senior citizen wages
"""

import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WriteBackStatus(str, Enum):
    """Status of a write-back operation."""
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class W2Box12Code(str, Enum):
    """OBBB W-2 Box 12 codes."""
    TT = "TT"  # Qualified overtime + tips
    TP = "TP"  # Qualified tips only
    TS = "TS"  # Qualified senior wages


class WriteBackRecord(BaseModel):
    """Record of a write-back operation."""
    id: UUID | None = None
    organization_id: UUID
    employee_id: UUID
    employee_external_id: str
    provider: str
    tax_year: int

    # W-2 values
    box_12_values: dict[str, Decimal] = Field(default_factory=dict)

    # Status tracking
    status: WriteBackStatus = WriteBackStatus.PENDING
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    error_message: str | None = None

    # Audit trail
    calculation_run_id: UUID | None = None
    vault_entry_id: UUID | None = None

    # Rollback info
    previous_values: dict[str, Decimal] | None = None


class WriteBackBatch(BaseModel):
    """Batch of write-back operations."""
    organization_id: UUID
    calculation_run_id: UUID
    tax_year: int
    provider: str

    records: list[WriteBackRecord] = Field(default_factory=list)

    # Aggregate
    total_records: int = 0
    completed_records: int = 0
    failed_records: int = 0

    status: WriteBackStatus = WriteBackStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class WriteBackEngine:
    """
    Manages the write-back of calculated OBBB values to payroll systems.

    All write-backs require explicit approval before transmission.
    """

    def __init__(self, db_session):
        self.db = db_session

    async def prepare_batch(
        self,
        organization_id: UUID,
        calculation_run_id: UUID,
        provider: str,
    ) -> WriteBackBatch:
        """
        Prepare a batch of write-back records from approved calculations.

        Args:
            organization_id: Organization to write back for
            calculation_run_id: Calculation run with approved results
            provider: Target payroll provider

        Returns:
            WriteBackBatch ready for approval
        """
        from sqlalchemy import select
        from backend.models.employee_calculation import EmployeeCalculation
        from backend.models.employee import Employee

        # Get approved calculations from this run
        result = await self.db.execute(
            select(EmployeeCalculation).where(
                EmployeeCalculation.calculation_run_id == calculation_run_id
            )
        )
        calculations = result.scalars().all()

        batch = WriteBackBatch(
            organization_id=organization_id,
            calculation_run_id=calculation_run_id,
            tax_year=datetime.utcnow().year,
            provider=provider,
        )

        for calc in calculations:
            # Get employee external ID
            emp_result = await self.db.execute(
                select(Employee).where(Employee.id == calc.employee_id)
            )
            employee = emp_result.scalar_one_or_none()
            if not employee:
                continue

            external_ids = employee.external_ids or {}
            external_id = external_ids.get(provider, "")
            if not external_id:
                logger.warning(
                    f"No {provider} external ID for employee {employee.id}"
                )
                continue

            # Build Box 12 values
            box_12 = self._calculate_box_12_values(calc)

            if any(v > Decimal("0") for v in box_12.values()):
                record = WriteBackRecord(
                    organization_id=organization_id,
                    employee_id=calc.employee_id,
                    employee_external_id=external_id,
                    provider=provider,
                    tax_year=batch.tax_year,
                    box_12_values=box_12,
                    calculation_run_id=calculation_run_id,
                )
                batch.records.append(record)

        batch.total_records = len(batch.records)
        return batch

    def _calculate_box_12_values(self, calc) -> dict[str, Decimal]:
        """Calculate W-2 Box 12 values from an employee calculation."""
        values: dict[str, Decimal] = {}

        ot_premium = getattr(calc, "qualified_ot_premium", None) or Decimal("0")
        tip_credit = getattr(calc, "qualified_tip_credit", None) or Decimal("0")
        phase_out_pct = getattr(calc, "phase_out_percentage", None) or Decimal("0")

        # Apply phase-out
        phase_out_multiplier = Decimal("1") - (phase_out_pct / Decimal("100"))

        # TT: Combined overtime + tips
        combined = (ot_premium + tip_credit) * phase_out_multiplier
        if combined > Decimal("0"):
            values[W2Box12Code.TT.value] = combined.quantize(Decimal("0.01"))

        # TP: Tips only (subset of TT)
        tips_only = tip_credit * phase_out_multiplier
        if tips_only > Decimal("0"):
            values[W2Box12Code.TP.value] = tips_only.quantize(Decimal("0.01"))

        # TS: Senior wages (if applicable)
        senior_wages = getattr(calc, "qualified_senior_wages", None) or Decimal("0")
        if senior_wages > Decimal("0"):
            values[W2Box12Code.TS.value] = (
                senior_wages * phase_out_multiplier
            ).quantize(Decimal("0.01"))

        return values

    async def approve_batch(
        self,
        batch: WriteBackBatch,
        approved_by: UUID,
    ) -> WriteBackBatch:
        """Mark a batch as approved for transmission."""
        batch.status = WriteBackStatus.APPROVED
        for record in batch.records:
            record.status = WriteBackStatus.APPROVED
            record.approved_by = approved_by
            record.approved_at = datetime.utcnow()
        return batch

    async def execute_batch(
        self,
        batch: WriteBackBatch,
    ) -> WriteBackBatch:
        """
        Execute write-back for all approved records in the batch.

        Connects to the payroll provider and pushes W-2 values.
        """
        if batch.status != WriteBackStatus.APPROVED:
            raise ValueError("Batch must be approved before execution")

        batch.status = WriteBackStatus.IN_PROGRESS
        integration = await self._get_integration(
            batch.organization_id, batch.provider
        )

        if not integration:
            batch.status = WriteBackStatus.FAILED
            logger.error(f"No integration found for provider {batch.provider}")
            return batch

        for record in batch.records:
            try:
                record.status = WriteBackStatus.IN_PROGRESS
                success = await integration.write_w2_values(
                    employee_external_id=record.employee_external_id,
                    box_12_values=record.box_12_values,
                )

                if success:
                    record.status = WriteBackStatus.COMPLETED
                    record.executed_at = datetime.utcnow()
                    batch.completed_records += 1

                    # Record in compliance vault
                    await self._record_vault_entry(record)
                else:
                    record.status = WriteBackStatus.FAILED
                    record.error_message = "Provider returned failure"
                    batch.failed_records += 1

            except Exception as e:
                record.status = WriteBackStatus.FAILED
                record.error_message = str(e)
                batch.failed_records += 1
                logger.error(
                    f"Write-back failed for employee {record.employee_external_id}: {e}"
                )

        # Update batch status
        if batch.failed_records == 0:
            batch.status = WriteBackStatus.COMPLETED
        elif batch.completed_records == 0:
            batch.status = WriteBackStatus.FAILED
        else:
            batch.status = WriteBackStatus.COMPLETED  # Partial success

        batch.completed_at = datetime.utcnow()
        return batch

    async def rollback_record(
        self,
        record: WriteBackRecord,
        reason: str,
    ) -> WriteBackRecord:
        """
        Rollback a completed write-back by writing zero values.

        This reverses the W-2 Box 12 entries.
        """
        integration = await self._get_integration(
            record.organization_id, record.provider
        )

        if not integration:
            raise ValueError(f"No integration for provider {record.provider}")

        # Store current values for audit trail
        record.previous_values = record.box_12_values.copy()

        # Write zeros to reverse
        zero_values = {code: Decimal("0") for code in record.box_12_values}
        success = await integration.write_w2_values(
            employee_external_id=record.employee_external_id,
            box_12_values=zero_values,
        )

        if success:
            record.status = WriteBackStatus.ROLLED_BACK
            record.error_message = f"Rolled back: {reason}"
            await self._record_vault_entry(record, action="rollback")
        else:
            raise RuntimeError("Rollback failed - manual intervention required")

        return record

    async def _get_integration(self, org_id: UUID, provider: str):
        """Get a configured integration instance for the provider."""
        from sqlalchemy import select
        from backend.models.integration import Integration
        from integrations.oauth_manager import OAuthTokenManager

        result = await self.db.execute(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.provider == provider,
                Integration.status == "connected",
            )
        )
        integration_record = result.scalar_one_or_none()
        if not integration_record:
            return None

        # Decrypt tokens
        from backend.config import get_settings
        settings = get_settings()
        token_manager = OAuthTokenManager(settings.encryption_key)

        access_token, refresh_token = token_manager.decrypt_tokens(
            integration_record.access_token_encrypted,
            integration_record.refresh_token_encrypted,
        )

        # Create provider-specific integration
        return self._create_integration_client(
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            config=integration_record.provider_metadata or {},
        )

    def _create_integration_client(
        self,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        config: dict,
    ):
        """Factory to create provider-specific integration clients."""
        from integrations.payroll.adp import ADPIntegration
        from integrations.payroll.gusto import GustoIntegration
        from integrations.payroll.paychex import PaychexIntegration
        from integrations.payroll.quickbooks_payroll import QuickBooksPayrollIntegration

        clients = {
            "adp": ADPIntegration,
            "gusto": GustoIntegration,
            "paychex": PaychexIntegration,
            "quickbooks": QuickBooksPayrollIntegration,
        }

        client_class = clients.get(provider)
        if not client_class:
            raise ValueError(f"Unsupported provider: {provider}")

        return client_class(
            access_token=access_token,
            refresh_token=refresh_token,
            config=config,
        )

    async def _record_vault_entry(
        self,
        record: WriteBackRecord,
        action: str = "write_back",
    ):
        """Record write-back action in compliance vault."""
        try:
            from compliance_vault.ledger import ComplianceVaultLedger

            ledger = ComplianceVaultLedger(self.db)
            await ledger.append(
                organization_id=record.organization_id,
                entry_type="write_back",
                content={
                    "action": action,
                    "employee_id": str(record.employee_id),
                    "provider": record.provider,
                    "box_12_values": {
                        k: str(v) for k, v in record.box_12_values.items()
                    },
                    "previous_values": (
                        {k: str(v) for k, v in record.previous_values.items()}
                        if record.previous_values else None
                    ),
                    "calculation_run_id": str(record.calculation_run_id)
                    if record.calculation_run_id else None,
                    "approved_by": str(record.approved_by)
                    if record.approved_by else None,
                },
                actor_id=record.approved_by,
            )
        except Exception as e:
            logger.error(f"Failed to record vault entry: {e}")
