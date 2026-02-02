"""
Write-Back Engine Unit Tests

Tests for W-2 Box 12 value calculation, model defaults,
batch approval, and batch execution guard.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.services.writeback_engine import (
    W2Box12Code,
    WriteBackBatch,
    WriteBackEngine,
    WriteBackRecord,
    WriteBackStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_calc(
    ot_premium: Decimal = Decimal("0"),
    tip_credit: Decimal = Decimal("0"),
    phase_out_pct: Decimal = Decimal("0"),
    senior_wages: Decimal = Decimal("0"),
) -> SimpleNamespace:
    """Return a lightweight calc object with the attributes the engine reads."""
    return SimpleNamespace(
        qualified_ot_premium=ot_premium,
        qualified_tip_credit=tip_credit,
        phase_out_percentage=phase_out_pct,
        qualified_senior_wages=senior_wages,
    )


def _engine() -> WriteBackEngine:
    """Return a WriteBackEngine with a dummy db session (not used in sync tests)."""
    return WriteBackEngine(db_session=None)


def _sample_record(**overrides) -> WriteBackRecord:
    """Return a WriteBackRecord with sensible defaults, accepting overrides."""
    defaults = dict(
        organization_id=uuid4(),
        employee_id=uuid4(),
        employee_external_id="EXT-001",
        provider="gusto",
        tax_year=2025,
    )
    defaults.update(overrides)
    return WriteBackRecord(**defaults)


def _sample_batch(records: list[WriteBackRecord] | None = None, **overrides) -> WriteBackBatch:
    """Return a WriteBackBatch with sensible defaults, accepting overrides."""
    defaults = dict(
        organization_id=uuid4(),
        calculation_run_id=uuid4(),
        tax_year=2025,
        provider="gusto",
        records=records or [],
        total_records=len(records) if records else 0,
    )
    defaults.update(overrides)
    return WriteBackBatch(**defaults)


# ---------------------------------------------------------------------------
# Box 12 Calculation Tests
# ---------------------------------------------------------------------------

class TestCalculateBox12Values:
    """Tests for WriteBackEngine._calculate_box_12_values."""

    def test_no_phase_out(self):
        """No phase-out (0%) -- both TT and TP populated with full values."""
        calc = _make_calc(ot_premium=Decimal("200.00"), tip_credit=Decimal("100.00"))
        result = _engine()._calculate_box_12_values(calc)

        assert result[W2Box12Code.TT.value] == Decimal("300.00")
        assert result[W2Box12Code.TP.value] == Decimal("100.00")
        assert W2Box12Code.TS.value not in result

    def test_50_percent_phase_out(self):
        """50% phase-out halves every value."""
        calc = _make_calc(
            ot_premium=Decimal("200.00"),
            tip_credit=Decimal("100.00"),
            phase_out_pct=Decimal("50"),
        )
        result = _engine()._calculate_box_12_values(calc)

        assert result[W2Box12Code.TT.value] == Decimal("150.00")
        assert result[W2Box12Code.TP.value] == Decimal("50.00")

    def test_100_percent_phase_out_zeroes_all_codes(self):
        """100% phase-out zeroes everything.

        TT and TP are excluded because their post-multiplier check catches
        the zero.  TS is still present because the engine gates on the raw
        (pre-multiplier) senior_wages value, so a zero-valued entry appears.
        """
        calc = _make_calc(
            ot_premium=Decimal("200.00"),
            tip_credit=Decimal("100.00"),
            phase_out_pct=Decimal("100"),
            senior_wages=Decimal("500.00"),
        )
        result = _engine()._calculate_box_12_values(calc)

        # TT and TP are gated on the post-multiplier value, so they vanish.
        assert W2Box12Code.TT.value not in result
        assert W2Box12Code.TP.value not in result

        # TS is gated on raw senior_wages (> 0), so it appears with value 0.00.
        assert result[W2Box12Code.TS.value] == Decimal("0.00")

    def test_only_overtime_no_tips(self):
        """Only overtime premium -- TT populated, TP absent."""
        calc = _make_calc(ot_premium=Decimal("400.00"))
        result = _engine()._calculate_box_12_values(calc)

        assert result[W2Box12Code.TT.value] == Decimal("400.00")
        assert W2Box12Code.TP.value not in result

    def test_only_tips(self):
        """Only tip credit -- TT equals TP (combined = tips when OT is 0)."""
        calc = _make_calc(tip_credit=Decimal("250.00"))
        result = _engine()._calculate_box_12_values(calc)

        assert result[W2Box12Code.TT.value] == Decimal("250.00")
        assert result[W2Box12Code.TP.value] == Decimal("250.00")
        assert result[W2Box12Code.TT.value] == result[W2Box12Code.TP.value]

    def test_senior_wages_code_present(self):
        """Senior wages produce a TS code; TT and TP remain absent."""
        calc = _make_calc(senior_wages=Decimal("1000.00"))
        result = _engine()._calculate_box_12_values(calc)

        assert result[W2Box12Code.TS.value] == Decimal("1000.00")
        # No OT or tips, so TT and TP should be absent
        assert W2Box12Code.TT.value not in result
        assert W2Box12Code.TP.value not in result


# ---------------------------------------------------------------------------
# Model Default Tests
# ---------------------------------------------------------------------------

class TestModelDefaults:
    """Tests for Pydantic model default values."""

    def test_record_defaults_to_pending(self):
        """WriteBackRecord status defaults to PENDING."""
        record = _sample_record()
        assert record.status == WriteBackStatus.PENDING

    def test_batch_defaults_to_pending(self):
        """WriteBackBatch status defaults to PENDING."""
        batch = _sample_batch()
        assert batch.status == WriteBackStatus.PENDING


# ---------------------------------------------------------------------------
# Batch Approval Tests
# ---------------------------------------------------------------------------

class TestApproveBatch:
    """Tests for WriteBackEngine.approve_batch."""

    @pytest.mark.asyncio
    async def test_approve_batch_sets_status_and_audit_fields(self):
        """approve_batch marks batch and every record as APPROVED with audit info."""
        approver_id = uuid4()
        records = [_sample_record(), _sample_record()]
        batch = _sample_batch(records=records)

        engine = _engine()
        before = datetime.utcnow()
        result = await engine.approve_batch(batch, approved_by=approver_id)
        after = datetime.utcnow()

        assert result.status == WriteBackStatus.APPROVED

        for record in result.records:
            assert record.status == WriteBackStatus.APPROVED
            assert record.approved_by == approver_id
            assert record.approved_at is not None
            assert before <= record.approved_at <= after


# ---------------------------------------------------------------------------
# Batch Execution Guard Test
# ---------------------------------------------------------------------------

class TestExecuteBatch:
    """Tests for WriteBackEngine.execute_batch pre-condition."""

    @pytest.mark.asyncio
    async def test_execute_batch_raises_if_not_approved(self):
        """execute_batch raises ValueError when batch is still PENDING."""
        batch = _sample_batch()
        assert batch.status == WriteBackStatus.PENDING

        engine = _engine()
        with pytest.raises(ValueError, match="Batch must be approved before execution"):
            await engine.execute_batch(batch)
