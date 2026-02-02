"""
Base Model Classes and Mixins

Provides foundational patterns for all SafeHarbor database models.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Declarative base for all SafeHarbor models.

    Provides common type annotations and metadata configuration.
    """

    type_annotation_map: dict[type, Any] = {}


class TimestampMixin:
    """
    Mixin for automatic created_at and updated_at timestamps.

    Automatically sets created_at on insert and updated_at on every update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when record was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when record was last updated",
    )


class AuditMixin:
    """
    Mixin for full audit trail with Compliance Vault reference.

    Tracks who created/modified records and links to immutable vault entries.
    Use this for models that require IRS-defensible audit trails.
    """

    created_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User ID who created this record",
    )
    modified_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User ID who last modified this record",
    )
    vault_entry_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="Reference to compliance_vault entry for this mutation",
    )
