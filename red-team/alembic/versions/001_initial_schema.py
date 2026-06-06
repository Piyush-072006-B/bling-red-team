"""001_initial_schema

Initial Red Team database schema.
Creates 3 tables:
  - ingest_log:        records every incoming fraud signal
  - evasion_kb:        append-only evasion knowledge base
  - red_team_reports:  one report per evasion analysis batch

Revision ID: 001
Revises: (none — initial migration)
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────────
    # Table: ingest_log
    # Records every incoming signal from Blue Team.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "ingest_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum(
                "FRAUD_DNA",
                "NOVELTY",
                "GATE_MISS",
                name="ingest_source_type_enum",
            ),
            nullable=False,
            comment="Type of inbound signal from Blue Team",
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Full inbound payload as received (may contain hashed IDs)",
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="QUEUED",
            comment="Processing status: QUEUED | PROCESSING | DONE | DUPLICATE | ERROR",
        ),
        sa.Column(
            "priority",
            sa.String(16),
            nullable=True,
            comment="Assigned priority: LOW | MEDIUM | HIGH | CRITICAL",
        ),
        sa.Column(
            "transaction_id_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 hash prefix of transaction_id for dedup (no raw IDs stored)",
        ),
    )

    op.create_index(
        "ix_ingest_log_received_at",
        "ingest_log",
        ["received_at"],
    )
    op.create_index(
        "ix_ingest_log_source_type",
        "ingest_log",
        ["source_type"],
    )
    op.create_index(
        "ix_ingest_log_transaction_id_hash",
        "ingest_log",
        ["transaction_id_hash"],
        unique=False,
    )
    op.create_index(
        "ix_ingest_log_status",
        "ingest_log",
        ["status"],
    )

    # ─────────────────────────────────────────────────────────────
    # Table: evasion_kb
    # Append-only knowledge base. Never updated or deleted.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "evasion_kb",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "archetype",
            sa.String(64),
            nullable=False,
            comment="One of 16 known archetypes or NEW_VARIANT",
        ),
        sa.Column(
            "evasion_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="The mutated feature vector that achieved evasion",
        ),
        sa.Column(
            "gate_bypassed",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            comment="Which of the 5 hard gates were bypassed (if any)",
        ),
        sa.Column(
            "feature_deltas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Delta between original and evasion vector per feature",
        ),
        sa.Column(
            "context_multiplier_abused",
            sa.String(128),
            nullable=True,
            comment="Which Indian context multiplier was exploited (e.g. is_festival_period)",
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="evasion_severity_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "evasion_success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if mutated score dropped below 0.50 from >= 0.75",
        ),
        sa.Column(
            "score_original",
            sa.Float(),
            nullable=True,
            comment="Blue Team shadow scorer score on original vector",
        ),
        sa.Column(
            "score_mutated",
            sa.Float(),
            nullable=True,
            comment="Blue Team shadow scorer score on mutated vector",
        ),
        sa.Column(
            "ingest_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_log.id", ondelete="SET NULL"),
            nullable=True,
            comment="Reference to the triggering ingest signal",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_evasion_kb_archetype",
        "evasion_kb",
        ["archetype"],
    )
    op.create_index(
        "ix_evasion_kb_severity",
        "evasion_kb",
        ["severity"],
    )
    op.create_index(
        "ix_evasion_kb_created_at",
        "evasion_kb",
        ["created_at"],
    )
    op.create_index(
        "ix_evasion_kb_evasion_success",
        "evasion_kb",
        ["evasion_success"],
    )

    # ─────────────────────────────────────────────────────────────
    # Table: red_team_reports
    # One report per evasion batch — proposals for developers.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "red_team_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "report_type",
            sa.Enum(
                "GATE_PATCH",
                "NEW_ARCHETYPE",
                "CONTEXT_ABUSE",
                name="report_type_enum",
            ),
            nullable=False,
            comment="Category of the evasion finding",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Full report detail: mutations, gate vulnerabilities, recommendations",
        ),
        sa.Column(
            "recommended_action",
            sa.Enum(
                "PATCH",
                "MONITOR",
                "ACCEPT",
                name="recommended_action_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "ingest_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_log.id", ondelete="SET NULL"),
            nullable=True,
            comment="Reference to the triggering ingest signal",
        ),
        sa.Column(
            "evasion_kb_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
            comment="UUIDs of evasion_kb rows that contributed to this report",
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="report_severity_enum",
            ),
            nullable=True,
            comment="Highest severity among contributing evasion_kb entries",
        ),
        sa.Column(
            "tgep_webhook_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this report was sent to TGEP webhook",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_red_team_reports_report_type",
        "red_team_reports",
        ["report_type"],
    )
    op.create_index(
        "ix_red_team_reports_recommended_action",
        "red_team_reports",
        ["recommended_action"],
    )
    op.create_index(
        "ix_red_team_reports_created_at",
        "red_team_reports",
        ["created_at"],
    )
    op.create_index(
        "ix_red_team_reports_tgep_webhook_sent",
        "red_team_reports",
        ["tgep_webhook_sent"],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("red_team_reports")
    op.drop_table("evasion_kb")
    op.drop_table("ingest_log")

    # Drop custom enum types
    op.execute("DROP TYPE IF EXISTS report_severity_enum")
    op.execute("DROP TYPE IF EXISTS recommended_action_enum")
    op.execute("DROP TYPE IF EXISTS report_type_enum")
    op.execute("DROP TYPE IF EXISTS evasion_severity_enum")
    op.execute("DROP TYPE IF EXISTS ingest_source_type_enum")
