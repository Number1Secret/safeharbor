"""
Authentication Service

Handles password hashing, JWT creation/validation, and auth business logic.
"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from backend.config import get_settings

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    sub: str,
    email: str,
    org_id: str,
    role: str,
) -> str:
    """
    Create a JWT access token.

    Claims match the contract in backend/middleware/rbac.py _validate_token():
      - sub: str(user.id)
      - email: user.email
      - org_id: str(user.organization_id)
      - role: user.role
      - type: "access"
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "org_id": org_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(
    sub: str,
    org_id: str,
) -> str:
    """Create a JWT refresh token (longer-lived, fewer claims)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "org_id": org_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
