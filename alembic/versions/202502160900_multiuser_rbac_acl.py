"""Multi-user RBAC/ACL, personal delivery, feedback inbox."""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202502160900"
down_revision = "202412211200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_users_tg_user", "users", type_="unique")
    op.alter_column("users", "tg_user_id", new_column_name="telegram_user_id")
    op.create_unique_constraint("uq_users_telegram_user", "users", ["telegram_user_id"])

    op.add_column("users", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("UPDATE users SET status = 'active' WHERE status IS NULL")
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
    op.execute("UPDATE users SET is_active = (status = 'active')")
    op.execute("UPDATE users SET last_seen_at = created_at WHERE last_seen_at IS NULL")

    op.add_column(
        "categories",
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    admin_id = os.getenv("TELEGRAM_ADMIN_USER_ID")
    if admin_id:
        admin_id_value = int(admin_id)
        op.execute(
            "UPDATE categories SET owner_user_id = users.id "
            f"FROM users WHERE users.telegram_user_id = {admin_id_value} "
            "AND categories.owner_user_id IS NULL"
        )
    else:
        op.execute(
            "UPDATE categories SET owner_user_id = ("
            "SELECT id FROM users ORDER BY created_at ASC LIMIT 1"
            ") WHERE owner_user_id IS NULL"
        )

    op.create_table(
        "category_acl",
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("category_id", "user_id"),
        sa.UniqueConstraint("category_id", "user_id", name="uq_category_acl"),
    )

    op.create_table(
        "user_category_delivery",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Text(),
            server_default="instant",
            nullable=False,
        ),
        sa.Column("digest_kind", sa.Text(), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("daily_time_hhmm", sa.Text(), nullable=True),
        sa.Column(
            "timezone",
            sa.Text(),
            server_default="Europe/Berlin",
            nullable=False,
        ),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "category_id"),
        sa.UniqueConstraint("user_id", "category_id", name="uq_user_category_delivery"),
    )

    op.create_table(
        "user_category_chat_delivery_override",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column("digest_kind", sa.Text(), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("daily_time_hhmm", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "category_id", "chat_id"),
        sa.UniqueConstraint(
            "user_id",
            "category_id",
            "chat_id",
            name="uq_user_category_chat_override",
        ),
    )

    op.create_table(
        "feedback_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("feedback_messages")
    op.drop_table("user_category_chat_delivery_override")
    op.drop_table("user_category_delivery")
    op.drop_table("category_acl")
    op.drop_column("categories", "owner_user_id")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "status")
    op.drop_column("users", "role")
    op.drop_column("users", "first_name")
    op.drop_constraint("uq_users_telegram_user", "users", type_="unique")
    op.alter_column("users", "telegram_user_id", new_column_name="tg_user_id")
    op.create_unique_constraint("uq_users_tg_user", "users", ["tg_user_id"])
