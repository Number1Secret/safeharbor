"""
OAuth Token Manager

Manages OAuth token lifecycle including encryption, storage, and refresh.
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Handles encryption/decryption of OAuth tokens."""

    def __init__(self, encryption_key: str | bytes):
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        self.cipher = Fernet(encryption_key)

    def encrypt(self, token: str) -> bytes:
        """Encrypt a token string."""
        return self.cipher.encrypt(token.encode())

    def decrypt(self, encrypted_token: bytes) -> str:
        """Decrypt an encrypted token."""
        return self.cipher.decrypt(encrypted_token).decode()


class OAuthTokenManager:
    """
    Manages OAuth token lifecycle for integrations.

    Handles:
    - Token encryption at rest
    - Token refresh before expiry
    - Token storage in database
    """

    def __init__(self, encryption_key: str | bytes):
        self.encryption = TokenEncryption(encryption_key)
        self._token_buffer_minutes = 5  # Refresh tokens 5 min before expiry

    def encrypt_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
    ) -> tuple[bytes, bytes | None]:
        """
        Encrypt tokens for storage.

        Returns:
            Tuple of (encrypted_access, encrypted_refresh)
        """
        encrypted_access = self.encryption.encrypt(access_token)
        encrypted_refresh = None
        if refresh_token:
            encrypted_refresh = self.encryption.encrypt(refresh_token)
        return encrypted_access, encrypted_refresh

    def decrypt_tokens(
        self,
        encrypted_access: bytes,
        encrypted_refresh: bytes | None = None,
    ) -> tuple[str, str | None]:
        """
        Decrypt stored tokens.

        Returns:
            Tuple of (access_token, refresh_token)
        """
        access_token = self.encryption.decrypt(encrypted_access)
        refresh_token = None
        if encrypted_refresh:
            refresh_token = self.encryption.decrypt(encrypted_refresh)
        return access_token, refresh_token

    def needs_refresh(
        self,
        expires_at: datetime | None,
    ) -> bool:
        """Check if token needs refresh (within buffer period)."""
        if not expires_at:
            return False
        buffer = timedelta(minutes=self._token_buffer_minutes)
        return datetime.utcnow() + buffer >= expires_at

    async def get_valid_token(
        self,
        encrypted_access: bytes,
        encrypted_refresh: bytes | None,
        expires_at: datetime | None,
        refresh_callback,
    ) -> tuple[str, bytes, bytes | None, datetime | None]:
        """
        Get a valid access token, refreshing if necessary.

        Args:
            encrypted_access: Encrypted access token
            encrypted_refresh: Encrypted refresh token
            expires_at: Token expiration time
            refresh_callback: Async function to call for refresh

        Returns:
            Tuple of (access_token, new_encrypted_access, new_encrypted_refresh, new_expires_at)
        """
        access_token, refresh_token = self.decrypt_tokens(
            encrypted_access, encrypted_refresh
        )

        if not self.needs_refresh(expires_at):
            return access_token, encrypted_access, encrypted_refresh, expires_at

        if not refresh_token:
            logger.warning("Token expired but no refresh token available")
            return access_token, encrypted_access, encrypted_refresh, expires_at

        # Refresh the token
        logger.info("Refreshing OAuth token...")
        new_access, new_refresh, expires_in = await refresh_callback(refresh_token)

        # Encrypt new tokens
        new_encrypted_access, new_encrypted_refresh = self.encrypt_tokens(
            new_access, new_refresh
        )

        # Calculate new expiry
        new_expires_at = None
        if expires_in:
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return new_access, new_encrypted_access, new_encrypted_refresh, new_expires_at


# OAuth configuration for supported providers
OAUTH_CONFIGS = {
    "adp": {
        "authorize_url": "https://accounts.adp.com/auth/oauth/v2/authorize",
        "token_url": "https://accounts.adp.com/auth/oauth/v2/token",
        "scopes": ["api"],
    },
    "gusto": {
        "authorize_url": "https://api.gusto.com/oauth/authorize",
        "token_url": "https://api.gusto.com/oauth/token",
        "scopes": ["employees:read", "payrolls:read", "companies:read"],
    },
    "paychex": {
        "authorize_url": "https://api.paychex.com/auth/oauth/v2/authorize",
        "token_url": "https://api.paychex.com/auth/oauth/v2/token",
        "scopes": ["employees", "payroll"],
    },
    "quickbooks": {
        "authorize_url": "https://appcenter.intuit.com/connect/oauth2",
        "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        "scopes": ["com.intuit.quickbooks.payroll"],
    },
    "toast": {
        "authorize_url": "https://ws-api.toasttab.com/authentication/v1/authentication/login",
        "token_url": "https://ws-api.toasttab.com/authentication/v1/authentication/login",
        "scopes": ["labor", "orders"],
    },
    "square": {
        "authorize_url": "https://connect.squareup.com/oauth2/authorize",
        "token_url": "https://connect.squareup.com/oauth2/token",
        "scopes": ["EMPLOYEES_READ", "TIMECARDS_READ", "MERCHANT_PROFILE_READ"],
    },
    "deputy": {
        "authorize_url": "https://once.deputy.com/my/oauth/login",
        "token_url": "https://once.deputy.com/my/oauth/access_token",
        "scopes": ["longlife_refresh_token"],
    },
    "bamboohr": {
        "authorize_url": "https://api.bamboohr.com/authorize",
        "token_url": "https://api.bamboohr.com/token",
        "scopes": ["employee:read"],
    },
}


def get_oauth_config(provider: str) -> dict | None:
    """Get OAuth configuration for a provider."""
    return OAUTH_CONFIGS.get(provider.lower())
