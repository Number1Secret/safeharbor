"""
SafeHarbor AI Configuration

Environment-based settings for the OBBB Tax Compliance Engine.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "SafeHarbor AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "safeharbor"
    postgres_password: str = "safeharbor"
    postgres_db: str = "safeharbor"

    @computed_field
    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        """Construct sync PostgreSQL URL for Alembic migrations."""
        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @computed_field
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        return str(
            RedisDsn.build(
                scheme="redis",
                host=self.redis_host,
                port=self.redis_port,
                path=str(self.redis_db),
            )
        )

    # Security
    secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32",
        description="Secret key for JWT signing and encryption",
    )
    encryption_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-fernet-generate-key",
        description="Fernet key for encrypting OAuth tokens",
    )
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Anthropic API
    anthropic_api_key: str = Field(
        default="",
        description="API key for Claude AI",
    )
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OBBB Tax Configuration
    tax_year: int = 2025
    federal_minimum_wage: float = 7.25
    flsa_overtime_threshold: int = 40  # hours per workweek

    # Phase-out thresholds (OBBB)
    phase_out_single_start: int = 75_000
    phase_out_single_end: int = 100_000
    phase_out_married_start: int = 150_000
    phase_out_married_end: int = 200_000
    phase_out_hoh_start: int = 112_500
    phase_out_hoh_end: int = 150_000

    # Compliance Vault
    vault_retention_years: int = 7

    # Integration Rate Limits (per hour unless specified)
    rate_limit_adp: int = 1000
    rate_limit_gusto: int = 6000  # 100/min
    rate_limit_toast: int = 30000  # 500/min
    rate_limit_square: int = 30000  # 500/min

    # SMTP / Email
    smtp_host: str = Field(default="", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_from_email: str = Field(default="noreply@safeharbor.ai", description="From email address")
    smtp_from_name: str = Field(default="SafeHarbor AI", description="From display name")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")

    # Error Monitoring
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error monitoring (leave empty to disable)",
    )

    # Feature Flags
    enable_penalty_guarantee: bool = False
    enable_enterprise_sso: bool = False
    enable_writeback: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
