"""
Tests for compliance vault hash chain integrity verification.

Tests verify_chain and verify_entry from compliance_vault.integrity
using real async database sessions with the ComplianceVault model.
"""

import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from backend.models.compliance_vault import ComplianceVault
from compliance_vault.integrity import verify_chain, verify_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(content: dict) -> str:
    """Compute the SHA-256 content hash matching ledger logic."""
    content_json = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(content_json.encode()).hexdigest()


def _entry_hash(previous_hash_value: str, content: dict, timestamp: datetime) -> str:
    """Compute the SHA-256 entry hash matching ledger logic.

    ``previous_hash_value`` should be ``"GENESIS"`` for the first entry,
    or the prior entry's ``entry_hash`` for subsequent entries.
    """
    content_json = json.dumps(content, sort_keys=True, default=str)
    hash_input = f"{previous_hash_value}|{content_json}|{timestamp.isoformat()}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


def _make_vault_entry(
    organization_id,
    sequence_number: int,
    content: dict,
    previous_hash: str | None,
    timestamp: datetime | None = None,
) -> ComplianceVault:
    """Build a correctly-hashed ComplianceVault instance.

    For the genesis entry (sequence 1), ``previous_hash`` should be ``None``.
    The hash computation uses ``"GENESIS"`` internally for that case.
    """
    ts = timestamp or datetime.utcnow()
    # For hash computation, use "GENESIS" when previous_hash is None (genesis entry)
    hash_prev = previous_hash if previous_hash is not None else "GENESIS"
    c_hash = _content_hash(content)
    e_hash = _entry_hash(hash_prev, content, ts)

    return ComplianceVault(
        id=uuid4(),
        organization_id=organization_id,
        entry_type="calculation_finalized",
        entry_hash=e_hash,
        previous_hash=previous_hash,  # None for genesis, hex string otherwise
        sequence_number=sequence_number,
        content=content,
        content_hash=c_hash,
        retention_expires_at=ts + timedelta(days=7 * 365),
        actor_id=None,
        actor_type="system",
        created_at=ts,
    )


async def _insert_chain(db_session, organization_id, count: int):
    """Insert *count* correctly-linked vault entries and return them."""
    entries = []
    prev_hash: str | None = None
    base_time = datetime.utcnow()

    for i in range(1, count + 1):
        content = {"action": "test", "seq": i, "data": f"payload-{i}"}
        ts = base_time + timedelta(seconds=i)
        entry = _make_vault_entry(
            organization_id=organization_id,
            sequence_number=i,
            content=content,
            previous_hash=prev_hash,
            timestamp=ts,
        )
        db_session.add(entry)
        entries.append(entry)
        prev_hash = entry.entry_hash

    await db_session.flush()
    return entries


# ---------------------------------------------------------------------------
# verify_chain tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_chain_empty_org(db_session, test_org):
    """An organization with no vault entries should be considered valid."""
    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is True
    assert result["total_entries"] == 0
    assert result["entries_checked"] == 0
    assert result["first_broken_entry"] is None


@pytest.mark.asyncio
async def test_verify_chain_single_entry(db_session, test_org):
    """A single valid genesis entry should pass verification."""
    content = {"action": "genesis", "value": 42}
    entry = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content,
        previous_hash=None,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is True
    assert result["total_entries"] == 1
    assert result["entries_checked"] == 1
    assert result["first_broken_entry"] is None


@pytest.mark.asyncio
async def test_verify_chain_multiple_valid_entries(db_session, test_org):
    """Three correctly chained entries should all pass verification."""
    entries = await _insert_chain(db_session, test_org.id, count=3)

    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is True
    assert result["total_entries"] == 3
    assert result["entries_checked"] == 3
    assert result["first_broken_entry"] is None
    assert len(entries) == 3  # sanity check


@pytest.mark.asyncio
async def test_verify_chain_broken_sequence(db_session, test_org):
    """A gap in sequence_number should be detected as invalid."""
    base_time = datetime.utcnow()

    # Insert entry with sequence 1
    content1 = {"action": "test", "seq": 1}
    ts1 = base_time + timedelta(seconds=1)
    entry1 = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content1,
        previous_hash=None,
        timestamp=ts1,
    )
    db_session.add(entry1)

    # Insert entry with sequence 3 (skipping 2) — still chain the hash correctly
    content3 = {"action": "test", "seq": 3}
    ts3 = base_time + timedelta(seconds=3)
    entry3 = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=3,
        content=content3,
        previous_hash=entry1.entry_hash,
        timestamp=ts3,
    )
    db_session.add(entry3)
    await db_session.flush()

    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is False
    assert result["first_broken_entry"] == 3
    assert "Sequence gap" in result["message"] or "expected 2" in result["message"]


@pytest.mark.asyncio
async def test_verify_chain_broken_hash_link(db_session, test_org):
    """previous_hash not matching the prior entry's entry_hash should fail."""
    base_time = datetime.utcnow()

    # Insert valid entry 1
    content1 = {"action": "test", "seq": 1}
    ts1 = base_time + timedelta(seconds=1)
    entry1 = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content1,
        previous_hash=None,
        timestamp=ts1,
    )
    db_session.add(entry1)

    # Insert entry 2 with a WRONG previous_hash
    content2 = {"action": "test", "seq": 2}
    ts2 = base_time + timedelta(seconds=2)
    wrong_previous_hash = hashlib.sha256(b"wrong").hexdigest()
    entry2 = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=2,
        content=content2,
        previous_hash=wrong_previous_hash,
        timestamp=ts2,
    )
    db_session.add(entry2)
    await db_session.flush()

    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is False
    assert result["first_broken_entry"] == 2
    assert "broken" in result["message"].lower() or "chain" in result["message"].lower()


@pytest.mark.asyncio
async def test_verify_chain_tampered_content(db_session, test_org):
    """content_hash not matching the actual content should be detected."""
    base_time = datetime.utcnow()

    content = {"action": "original", "amount": 100}
    ts = base_time + timedelta(seconds=1)
    entry = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content,
        previous_hash=None,
        timestamp=ts,
    )
    db_session.add(entry)
    await db_session.flush()

    # Tamper with the content after insertion (simulate DB-level tampering)
    entry.content = {"action": "tampered", "amount": 999999}
    await db_session.flush()

    result = await verify_chain(db_session, test_org.id)

    assert result["is_valid"] is False
    assert result["first_broken_entry"] == 1
    assert "content" in result["message"].lower() or "tamper" in result["message"].lower()


# ---------------------------------------------------------------------------
# verify_entry tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_entry_valid(db_session, test_org):
    """A single correctly-hashed entry should pass individual verification."""
    content = {"action": "audit_event", "detail": "all good"}
    entry = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content,
        previous_hash=None,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await verify_entry(db_session, entry.id)

    assert result["is_valid"] is True
    assert result["entry_sequence"] == 1
    assert "verified" in result["message"].lower()


@pytest.mark.asyncio
async def test_verify_entry_tampered(db_session, test_org):
    """An entry whose content no longer matches its content_hash should fail."""
    content = {"action": "original", "value": "secret"}
    ts = datetime.utcnow()
    entry = _make_vault_entry(
        organization_id=test_org.id,
        sequence_number=1,
        content=content,
        previous_hash=None,
        timestamp=ts,
    )
    db_session.add(entry)
    await db_session.flush()

    # Tamper with the content
    entry.content = {"action": "modified", "value": "hacked"}
    await db_session.flush()

    result = await verify_entry(db_session, entry.id)

    assert result["is_valid"] is False
    assert result["entry_sequence"] == 1
    assert "mismatch" in result["message"].lower() or "tamper" in result["message"].lower()
