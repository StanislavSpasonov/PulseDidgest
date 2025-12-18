"""Extend delivery settings and debug flags."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202407260900"
down_revision = "202407230900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("debug_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "categories",
        sa.Column("prefilter_min_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("prefilter_include_any", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("prefilter_exclude_any", postgresql.ARRAY(sa.Text()), nullable=True),
    )

    op.add_column(
        "category_groups",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "category_groups",
        sa.Column("delivery_mode", sa.Text(), nullable=False, server_default="instant"),
    )
    op.add_column(
        "category_groups",
        sa.Column("delivery_interval_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "category_groups",
        sa.Column("delivery_time_local", sa.Text(), nullable=True),
    )
    op.add_column(
        "category_groups",
        sa.Column(
            "delivery_tz",
            sa.Text(),
            nullable=False,
            server_default="Europe/Berlin",
        ),
    )
    op.add_column(
        "category_groups",
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("category_groups", "last_sent_at")
    op.drop_column("category_groups", "delivery_tz")
    op.drop_column("category_groups", "delivery_time_local")
    op.drop_column("category_groups", "delivery_interval_minutes")
    op.drop_column("category_groups", "delivery_mode")
    op.drop_column("category_groups", "is_enabled")
    op.drop_column("categories", "prefilter_exclude_any")
    op.drop_column("categories", "prefilter_include_any")
    op.drop_column("categories", "prefilter_min_length")
    op.drop_column("categories", "debug_enabled")
