"""Initial schema: all SafeHarbor models

Revision ID: a001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === organizations ===
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, comment="Legal business name"),
        sa.Column("ein", sa.String(10), nullable=False, unique=True, comment="Employer Identification Number"),
        sa.Column("tax_year", sa.Integer(), nullable=False, server_default="2025"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="starter"),
        sa.Column("tip_credit_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("overtime_credit_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("penalty_guarantee_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("workweek_start", sa.String(10), nullable=False, server_default="sunday"),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("primary_contact_email", sa.String(255), nullable=True),
        sa.Column("primary_contact_name", sa.String(255), nullable=True),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ein ~ '^[0-9]{2}-[0-9]{7}$'", name="valid_ein_format"),
        sa.CheckConstraint("tier IN ('starter', 'pro', 'enterprise')", name="valid_tier"),
        sa.CheckConstraint("status IN ('active', 'suspended', 'closed')", name="valid_status"),
        sa.CheckConstraint(
            "workweek_start IN ('sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="valid_workweek_start",
        ),
    )
    op.create_index("ix_organizations_ein", "organizations", ["ein"])
    op.create_index("ix_organizations_status", "organizations", ["status"])

    # === users ===
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invite_token", sa.String(255), nullable=True, unique=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sso_provider", sa.String(100), nullable=True),
        sa.Column("sso_external_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_org_role", "users", ["organization_id", "role"])
    op.create_index("ix_users_sso", "users", ["sso_provider", "sso_external_id"])

    # === api_keys ===
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_org_active", "api_keys", ["organization_id", "is_active"])

    # === ttoc_classifications (must be before employees due to FK) ===
    op.create_table(
        "ttoc_classifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),  # FK added after employees table
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("duties", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("employer_industry", sa.String(100), nullable=True),
        sa.Column("tip_frequency", sa.String(20), nullable=True),
        sa.Column("ttoc_code", sa.String(10), nullable=False),
        sa.Column("ttoc_description", sa.String(500), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("is_tipped_occupation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tip_percentage_estimate", sa.Float(), nullable=True),
        sa.Column("alternative_codes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_id", sa.String(50), nullable=False),
        sa.Column("model_temperature", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("is_human_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_overridden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_code", sa.String(10), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("overridden_by", sa.Uuid(), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("superseded_by", sa.Uuid(), sa.ForeignKey("ttoc_classifications.id"), nullable=True),
        sa.Column("classification_latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ttoc_classifications_employee_id", "ttoc_classifications", ["employee_id"])
    op.create_index("ix_ttoc_classifications_ttoc_code", "ttoc_classifications", ["ttoc_code"])
    op.create_index("ix_ttoc_classifications_is_active", "ttoc_classifications", ["is_active"])
    op.create_index("ix_ttoc_classifications_confidence", "ttoc_classifications", ["confidence_score"])
    op.create_index("ix_ttoc_classifications_employee_active", "ttoc_classifications", ["employee_id", "is_active"])

    # === employees ===
    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_ids", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("ssn_hash", sa.String(64), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("employment_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("duties", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("hourly_rate", sa.Float(), nullable=True),
        sa.Column("is_hourly", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("ttoc_code", sa.String(10), nullable=True),
        sa.Column("ttoc_classification_id", sa.Uuid(), sa.ForeignKey("ttoc_classifications.id"), nullable=True),
        sa.Column("ttoc_title", sa.String(20), nullable=True, comment="TTOC title category"),
        sa.Column("ttoc_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ttoc_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ttoc_verified_by", sa.Uuid(), nullable=True),
        sa.Column("filing_status", sa.String(30), nullable=True),
        sa.Column("estimated_annual_magi", sa.Float(), nullable=True),
        sa.Column("ytd_gross_wages", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ytd_overtime_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ytd_tips", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ytd_qualified_ot_premium", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ytd_qualified_tips", sa.Float(), nullable=False, server_default="0"),
        # AuditMixin
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("modified_by", sa.Uuid(), nullable=True),
        sa.Column("vault_entry_id", sa.Uuid(), nullable=True),
        # TimestampMixin
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "ssn_hash", name="uq_employee_org_ssn"),
    )
    op.create_index("ix_employees_organization_id", "employees", ["organization_id"])
    op.create_index("ix_employees_employment_status", "employees", ["employment_status"])
    op.create_index("ix_employees_ttoc_code", "employees", ["ttoc_code"])
    op.create_index("ix_employees_org_status", "employees", ["organization_id", "employment_status"])

    # Add FK from ttoc_classifications.employee_id -> employees.id
    op.create_foreign_key(
        "fk_ttoc_classifications_employee_id",
        "ttoc_classifications",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # === compliance_vault ===
    op.create_table(
        "compliance_vault",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("calculation_run_id", sa.Uuid(), nullable=True),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, comment="SHA-256 hash of content JSON"),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
        sa.Column("actor_ip", sa.String(45), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("entry_hash ~ '^[a-f0-9]{64}$'", name="valid_entry_hash"),
        sa.CheckConstraint("previous_hash IS NULL OR previous_hash ~ '^[a-f0-9]{64}$'", name="valid_previous_hash"),
        sa.CheckConstraint("retention_expires_at > created_at", name="valid_retention_date"),
    )
    op.create_index("ix_compliance_vault_org_id", "compliance_vault", ["organization_id"])
    op.create_index("ix_compliance_vault_entry_type", "compliance_vault", ["entry_type"])
    op.create_index("ix_compliance_vault_created_at", "compliance_vault", ["created_at"])
    op.create_index("ix_compliance_vault_employee_id", "compliance_vault", ["employee_id"])
    op.create_index("ix_compliance_vault_calculation_run_id", "compliance_vault", ["calculation_run_id"])
    op.create_index("ix_compliance_vault_retention", "compliance_vault", ["retention_expires_at"])
    op.create_index("ix_compliance_vault_org_sequence", "compliance_vault", ["organization_id", "sequence_number"])

    # === calculation_runs ===
    op.create_table(
        "calculation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_type", sa.String(30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_employees", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_employees", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_employees", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flagged_employees", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_qualified_ot_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_qualified_tips", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_combined_credit", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_phase_out_reduction", sa.Numeric(14, 2), nullable=True),
        sa.Column("previous_run_id", sa.Uuid(), sa.ForeignKey("calculation_runs.id"), nullable=True),
        sa.Column("delta_qualified_ot", sa.Numeric(14, 2), nullable=True),
        sa.Column("delta_qualified_tips", sa.Numeric(14, 2), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_vault_entry_id", sa.Uuid(), sa.ForeignKey("compliance_vault.id"), nullable=True),
        sa.Column("engine_versions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_completed_at", sa.DateTime(timezone=True), nullable=True),
        # AuditMixin
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("modified_by", sa.Uuid(), nullable=True),
        sa.Column("vault_entry_id", sa.Uuid(), nullable=True),
        # TimestampMixin
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("period_end >= period_start", name="valid_period_range"),
        sa.CheckConstraint(
            "run_type IN ('pay_period', 'quarterly', 'annual', 'ad_hoc', 'retro_audit')",
            name="valid_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'syncing', 'calculating', 'pending_approval', 'approved', 'rejected', 'finalized', 'error')",
            name="valid_run_status",
        ),
    )
    op.create_index("ix_calculation_runs_org_id", "calculation_runs", ["organization_id"])
    op.create_index("ix_calculation_runs_status", "calculation_runs", ["status"])
    op.create_index("ix_calculation_runs_org_period", "calculation_runs", ["organization_id", "period_start", "period_end"])
    op.create_index("ix_calculation_runs_tax_year", "calculation_runs", ["organization_id", "tax_year"])

    # === employee_calculations ===
    op.create_table(
        "employee_calculations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calculation_run_id", sa.Uuid(), sa.ForeignKey("calculation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        # Hours
        sa.Column("total_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("regular_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("overtime_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("state_overtime_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("double_time_hours", sa.Numeric(8, 2), nullable=True),
        # Compensation
        sa.Column("gross_wages", sa.Numeric(12, 2), nullable=True),
        sa.Column("hourly_rate_primary", sa.Numeric(8, 4), nullable=True),
        # FLSA Regular Rate
        sa.Column("regular_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("regular_rate_components", postgresql.JSONB(), nullable=False, server_default="{}"),
        # Overtime
        sa.Column("overtime_premium_calculated", sa.Numeric(10, 2), nullable=True),
        sa.Column("qualified_ot_premium", sa.Numeric(10, 2), nullable=True),
        # Tips
        sa.Column("cash_tips", sa.Numeric(10, 2), nullable=True),
        sa.Column("charged_tips", sa.Numeric(10, 2), nullable=True),
        sa.Column("tip_pool_out", sa.Numeric(10, 2), nullable=True),
        sa.Column("tip_pool_in", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_tips", sa.Numeric(10, 2), nullable=True),
        sa.Column("qualified_tips", sa.Numeric(10, 2), nullable=True),
        # TTOC
        sa.Column("ttoc_code", sa.String(10), nullable=True),
        sa.Column("ttoc_confidence", sa.Float(), nullable=True),
        sa.Column("ttoc_reasoning", sa.Text(), nullable=True),
        sa.Column("is_tipped_occupation", sa.Boolean(), nullable=False, server_default="false"),
        # Phase-out
        sa.Column("magi_estimated", sa.Numeric(12, 2), nullable=True),
        sa.Column("filing_status", sa.String(30), nullable=True),
        sa.Column("phase_out_threshold_start", sa.Numeric(12, 2), nullable=True),
        sa.Column("phase_out_threshold_end", sa.Numeric(12, 2), nullable=True),
        sa.Column("phase_out_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("phase_out_reduction_ot", sa.Numeric(10, 2), nullable=True),
        sa.Column("phase_out_reduction_tips", sa.Numeric(10, 2), nullable=True),
        # Final credits
        sa.Column("ot_credit_final", sa.Numeric(10, 2), nullable=True),
        sa.Column("tip_credit_final", sa.Numeric(10, 2), nullable=True),
        sa.Column("combined_credit_final", sa.Numeric(10, 2), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("anomaly_flags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        # Audit
        sa.Column("calculation_trace", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("input_data_hash", sa.String(64), nullable=True),
        sa.Column("engine_versions", postgresql.JSONB(), nullable=False, server_default="{}"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calculation_run_id", "employee_id", name="uq_run_employee"),
    )
    op.create_index("ix_employee_calculations_run_id", "employee_calculations", ["calculation_run_id"])
    op.create_index("ix_employee_calculations_employee_id", "employee_calculations", ["employee_id"])
    op.create_index("ix_employee_calculations_status", "employee_calculations", ["status"])

    # === integrations ===
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_category", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oauth_state", sa.String(255), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), nullable=True),
        sa.Column("last_sync_records", sa.Integer(), nullable=True),
        sa.Column("sync_cursor", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_id", sa.String(255), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", name="uq_org_provider"),
    )
    op.create_index("ix_integrations_organization_id", "integrations", ["organization_id"])
    op.create_index("ix_integrations_provider", "integrations", ["provider"])
    op.create_index("ix_integrations_status", "integrations", ["status"])
    op.create_index("ix_integrations_next_sync", "integrations", ["next_sync_at"])


def downgrade() -> None:
    # Drop circular FKs first to avoid dependency issues
    op.drop_constraint("fk_ttoc_classifications_employee_id", "ttoc_classifications", type_="foreignkey")
    op.drop_constraint("employees_ttoc_classification_id_fkey", "employees", type_="foreignkey")
    # Now drop tables in order
    op.drop_table("integrations")
    op.drop_table("employee_calculations")
    op.drop_table("calculation_runs")
    op.drop_table("compliance_vault")
    op.drop_table("ttoc_classifications")
    op.drop_table("employees")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
