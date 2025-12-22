"""Add delivery outbox table and source group username."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "202412211200"
down_revision = "202407260900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_groups", sa.Column("username", sa.Text(), nullable=True))
    op.add_column(
        "categories",
        sa.Column("default_delivery_mode", sa.Text(), server_default="instant", nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column("default_delivery_interval_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("default_delivery_time_local", sa.Text(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("default_delivery_tz", sa.Text(), server_default="Europe/Berlin", nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column("default_delivery_enabled", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_table(
        "delivery_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category_name", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("group_title", sa.Text(), nullable=True),
        sa.Column("group_username", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("delivery_outbox")
    op.drop_column("categories", "default_delivery_enabled")
    op.drop_column("categories", "default_delivery_tz")
    op.drop_column("categories", "default_delivery_time_local")
    op.drop_column("categories", "default_delivery_interval_minutes")
    op.drop_column("categories", "default_delivery_mode")
    op.drop_column("source_groups", "username")
