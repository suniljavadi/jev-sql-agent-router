"""Create application tables and adopt existing create_all databases."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "customers" not in existing:
        op.create_table(
            "customers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("region", sa.String(length=50), nullable=False),
            sa.Column("revenue", sa.Float(), nullable=False),
        )
    if "audit_events" not in existing:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_request", sa.Text(), nullable=False),
            sa.Column("generated_sql", sa.Text(), nullable=True),
            sa.Column("jev_decision", sa.JSON(), nullable=True),
            sa.Column("jev_confidence", sa.Float(), nullable=True),
            sa.Column("selected_action", sa.String(length=40), nullable=True),
            sa.Column("security_validation", sa.String(length=100), nullable=False),
            sa.Column("execution_status", sa.String(length=40), nullable=False),
            sa.Column("execution_time_ms", sa.Float(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("rows", sa.JSON(), nullable=False),
        )
    if "human_reviews" not in existing:
        op.create_table(
            "human_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("audit_id", sa.Integer(), sa.ForeignKey("audit_events.id"), nullable=False, unique=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("reviewer", sa.String(length=100), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_audit_id", sa.Integer(), sa.ForeignKey("audit_events.id"), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "human_reviews" in existing:
        op.drop_table("human_reviews")
    if "audit_events" in existing:
        op.drop_table("audit_events")
    if "customers" in existing:
        op.drop_table("customers")