"""
Unit tests for backend.services.auth

Covers password hashing/verification, JWT access & refresh token creation,
round-trip decoding, and failure modes (expired, invalid, tampered tokens).
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PASSWORD = "S3cure!Pa$$w0rd"
SAMPLE_SUB = "user-uuid-1234"
SAMPLE_EMAIL = "ada@example.com"
SAMPLE_ORG_ID = "org-uuid-5678"
SAMPLE_ROLE = "admin"


# ---------------------------------------------------------------------------
# 1. Password hashing produces different outputs (bcrypt salting)
# ---------------------------------------------------------------------------

def test_hash_password_produces_different_hashes_for_same_input():
    hash1 = hash_password(SAMPLE_PASSWORD)
    hash2 = hash_password(SAMPLE_PASSWORD)
    assert hash1 != hash2, "Bcrypt should produce unique hashes due to random salting"


# ---------------------------------------------------------------------------
# 2. Password verification succeeds for correct password
# ---------------------------------------------------------------------------

def test_verify_password_correct():
    hashed = hash_password(SAMPLE_PASSWORD)
    assert verify_password(SAMPLE_PASSWORD, hashed) is True


# ---------------------------------------------------------------------------
# 3. Password verification fails for wrong password
# ---------------------------------------------------------------------------

def test_verify_password_wrong():
    hashed = hash_password(SAMPLE_PASSWORD)
    assert verify_password("WrongPassword!", hashed) is False


# ---------------------------------------------------------------------------
# 4. Access token contains correct claims
# ---------------------------------------------------------------------------

def test_access_token_claims():
    token = create_access_token(
        sub=SAMPLE_SUB,
        email=SAMPLE_EMAIL,
        org_id=SAMPLE_ORG_ID,
        role=SAMPLE_ROLE,
    )
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

    assert payload["sub"] == SAMPLE_SUB
    assert payload["email"] == SAMPLE_EMAIL
    assert payload["org_id"] == SAMPLE_ORG_ID
    assert payload["role"] == SAMPLE_ROLE
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload


# ---------------------------------------------------------------------------
# 5. Access token has valid expiry (~60 minutes by default)
# ---------------------------------------------------------------------------

def test_access_token_expiry():
    before = datetime.now(timezone.utc)
    token = create_access_token(
        sub=SAMPLE_SUB,
        email=SAMPLE_EMAIL,
        org_id=SAMPLE_ORG_ID,
        role=SAMPLE_ROLE,
    )
    after = datetime.now(timezone.utc)

    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

    expected_delta = timedelta(minutes=settings.access_token_expire_minutes)
    # The difference between exp and iat should match the configured minutes
    actual_delta = exp - iat
    assert actual_delta == expected_delta

    # exp should be in the future relative to before the call
    assert exp > before


# ---------------------------------------------------------------------------
# 6. Refresh token contains correct claims
# ---------------------------------------------------------------------------

def test_refresh_token_claims():
    token = create_refresh_token(sub=SAMPLE_SUB, org_id=SAMPLE_ORG_ID)
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

    assert payload["sub"] == SAMPLE_SUB
    assert payload["org_id"] == SAMPLE_ORG_ID
    assert payload["type"] == "refresh"
    assert "iat" in payload
    assert "exp" in payload
    # Refresh tokens should NOT carry email or role
    assert "email" not in payload
    assert "role" not in payload


# ---------------------------------------------------------------------------
# 7. Refresh token has longer expiry than access token
# ---------------------------------------------------------------------------

def test_refresh_token_longer_expiry():
    access = create_access_token(
        sub=SAMPLE_SUB,
        email=SAMPLE_EMAIL,
        org_id=SAMPLE_ORG_ID,
        role=SAMPLE_ROLE,
    )
    refresh = create_refresh_token(sub=SAMPLE_SUB, org_id=SAMPLE_ORG_ID)

    access_payload = jwt.decode(access, settings.secret_key, algorithms=["HS256"])
    refresh_payload = jwt.decode(refresh, settings.secret_key, algorithms=["HS256"])

    access_exp = datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc)
    refresh_exp = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

    assert refresh_exp > access_exp, "Refresh token must expire later than access token"

    # Also verify absolute durations
    refresh_iat = datetime.fromtimestamp(refresh_payload["iat"], tz=timezone.utc)
    refresh_delta = refresh_exp - refresh_iat
    assert refresh_delta == timedelta(days=settings.refresh_token_expire_days)


# ---------------------------------------------------------------------------
# 8. decode_token round-trips correctly
# ---------------------------------------------------------------------------

def test_decode_token_roundtrip_access():
    token = create_access_token(
        sub=SAMPLE_SUB,
        email=SAMPLE_EMAIL,
        org_id=SAMPLE_ORG_ID,
        role=SAMPLE_ROLE,
    )
    payload = decode_token(token)

    assert payload["sub"] == SAMPLE_SUB
    assert payload["email"] == SAMPLE_EMAIL
    assert payload["org_id"] == SAMPLE_ORG_ID
    assert payload["role"] == SAMPLE_ROLE
    assert payload["type"] == "access"


def test_decode_token_roundtrip_refresh():
    token = create_refresh_token(sub=SAMPLE_SUB, org_id=SAMPLE_ORG_ID)
    payload = decode_token(token)

    assert payload["sub"] == SAMPLE_SUB
    assert payload["org_id"] == SAMPLE_ORG_ID
    assert payload["type"] == "refresh"


# ---------------------------------------------------------------------------
# 9. decode_token raises on expired token
# ---------------------------------------------------------------------------

def test_decode_token_expired():
    # Manually craft a token that already expired
    now = datetime.now(timezone.utc)
    payload = {
        "sub": SAMPLE_SUB,
        "email": SAMPLE_EMAIL,
        "org_id": SAMPLE_ORG_ID,
        "role": SAMPLE_ROLE,
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),  # expired 1 hour ago
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


# ---------------------------------------------------------------------------
# 10. decode_token raises on invalid token string
# ---------------------------------------------------------------------------

def test_decode_token_invalid_string():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("this.is.not.a.valid.jwt")


def test_decode_token_empty_string():
    with pytest.raises(jwt.DecodeError):
        decode_token("")


# ---------------------------------------------------------------------------
# 11. decode_token raises on tampered token (wrong secret)
# ---------------------------------------------------------------------------

def test_decode_token_tampered_wrong_secret():
    # Create a valid token signed with a different secret
    now = datetime.now(timezone.utc)
    payload = {
        "sub": SAMPLE_SUB,
        "email": SAMPLE_EMAIL,
        "org_id": SAMPLE_ORG_ID,
        "role": SAMPLE_ROLE,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, "completely-different-secret", algorithm="HS256")

    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token)
