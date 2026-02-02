"""
TTOCClassification Model

LLM-based Treasury Tipped Occupation Code classification.
Tracks AI decisions with full determinism envelope.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class TTOCClassification(TimestampMixin, Base):
    """
    LLM-based Treasury Tipped Occupation Code classification.

    Records the AI's classification decision with full reproducibility:
    - Input data (job title, description, duties)
    - Model and prompt versions (Determinism Envelope)
    - Output classification and confidence
    - Human verification/override tracking

    Multiple classifications can exist per employee (version history).
    The active classification is linked from Employee.ttoc_classification_id.
    """

    __tablename__ = "ttoc_classifications"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Classification input
    job_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Job title at time of classification",
    )
    job_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Job description text",
    )
    duties: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of job duties",
    )
    employer_industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Industry classification (restaurant, hospitality, etc.)",
    )
    tip_frequency: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="How often tips are received: always|frequently|occasionally|rarely|never",
    )

    # LLM classification output
    ttoc_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Assigned Treasury Tipped Occupation Code",
    )
    ttoc_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Official description of the TTOC code",
    )
    confidence_score: Mapped[float] = mapped_column(
        nullable=False,
        comment="AI confidence score (0.0-1.0)",
    )
    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AI reasoning for this classification",
    )

    # Classification result
    is_tipped_occupation: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether this occupation qualifies for tip exemption",
    )
    tip_percentage_estimate: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Estimated percentage of income from tips (0-100)",
    )

    # Alternative classifications considered
    alternative_codes: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Other possible TTOC codes with confidence scores",
    )

    # Determinism Envelope (for reproducibility)
    model_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="LLM model ID (e.g., claude-3-5-sonnet-20241022)",
    )
    model_temperature: Mapped[float] = mapped_column(
        default=0.0,
        comment="Temperature setting used (0 for determinism)",
    )
    prompt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Version of classification prompt (e.g., v1.0.0)",
    )
    prompt_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of the full prompt for reproducibility",
    )
    response_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of raw LLM response",
    )

    # Human verification/override
    is_human_verified: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether a human has verified this classification",
    )
    verified_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User who verified the classification",
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When classification was verified",
    )

    # Human override (if AI was wrong)
    is_overridden: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether human overrode the AI classification",
    )
    override_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Human-provided TTOC code if overriding AI",
    )
    override_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for override",
    )
    overridden_by: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="User who overrode the classification",
    )
    overridden_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When classification was overridden",
    )

    # Version tracking (can reclassify with newer models)
    classification_version: Mapped[int] = mapped_column(
        default=1,
        comment="Version number for this employee's classifications",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether this is the current active classification",
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("ttoc_classifications.id"),
        nullable=True,
        comment="Reference to newer classification that replaced this one",
    )

    # Processing metadata
    classification_latency_ms: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Time taken for LLM classification in milliseconds",
    )
    input_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Number of input tokens used",
    )
    output_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Number of output tokens generated",
    )

    __table_args__ = (
        Index("ix_ttoc_classifications_employee_id", "employee_id"),
        Index("ix_ttoc_classifications_ttoc_code", "ttoc_code"),
        Index("ix_ttoc_classifications_is_active", "is_active"),
        Index("ix_ttoc_classifications_confidence", "confidence_score"),
        Index("ix_ttoc_classifications_employee_active", "employee_id", "is_active"),
    )

    def __repr__(self) -> str:
        status = "verified" if self.is_human_verified else "ai"
        if self.is_overridden:
            status = "overridden"
        return f"<TTOCClassification {self.ttoc_code} ({status}) for employee={self.employee_id}>"

    @property
    def effective_ttoc_code(self) -> str:
        """Return the effective TTOC code (override if present, else AI)."""
        if self.is_overridden and self.override_code:
            return self.override_code
        return self.ttoc_code

    @property
    def confidence_level(self) -> str:
        """Return human-readable confidence level."""
        if self.confidence_score >= 0.9:
            return "high"
        elif self.confidence_score >= 0.7:
            return "medium"
        else:
            return "low"

    @property
    def needs_review(self) -> bool:
        """Check if classification needs human review."""
        return (
            not self.is_human_verified
            and not self.is_overridden
            and self.confidence_score < 0.9
        )
