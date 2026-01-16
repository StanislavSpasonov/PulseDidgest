"""SQLAlchemy models for persistence layer."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "source_chat_id",
            "source_message_id",
            name="uq_messages_source_chat_message",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_chat_id = Column(BigInteger, nullable=False)
    source_message_id = Column(BigInteger, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    decisions = relationship(
        "DecisionModel",
        back_populates="message",
        cascade="all, delete-orphan",
    )
    llm_errors = relationship(
        "LLMErrorModel",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class CategoryModel(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name = Column(Text, nullable=False, unique=True)
    prompt = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, server_default="true")
    debug_enabled = Column(Boolean, nullable=False, server_default="false")
    prefilter_min_length = Column(Integer, nullable=True)
    prefilter_include_any = Column(ARRAY(Text), nullable=True)
    prefilter_exclude_any = Column(ARRAY(Text), nullable=True)
    default_delivery_mode = Column(Text, nullable=False, server_default="instant")
    default_delivery_interval_minutes = Column(Integer, nullable=True)
    default_delivery_time_local = Column(Text, nullable=True)
    default_delivery_tz = Column(Text, nullable=False, server_default="Europe/Berlin")
    default_delivery_enabled = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    groups = relationship("CategoryGroupModel", cascade="all, delete-orphan")
    decisions = relationship("DecisionModel", back_populates="category")


class SourceGroupModel(Base):
    __tablename__ = "source_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tg_chat_id = Column(BigInteger, nullable=False, unique=True)
    title = Column(Text, nullable=True)
    username = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    categories = relationship("CategoryGroupModel", cascade="all, delete-orphan")


class CategoryGroupModel(Base):
    __tablename__ = "category_groups"
    __table_args__ = (
        UniqueConstraint("category_id", "group_id", name="pk_category_group"),
    )

    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("source_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_enabled = Column(Boolean, nullable=False, server_default="true")
    delivery_mode = Column(Text, nullable=False, server_default="instant")
    delivery_interval_minutes = Column(Integer, nullable=True)
    delivery_time_local = Column(Text, nullable=True)
    delivery_tz = Column(Text, nullable=False, server_default="Europe/Berlin")
    last_sent_at = Column(DateTime(timezone=True), nullable=True)


class LLMErrorModel(Base):
    __tablename__ = "llm_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    error_code = Column(Text, nullable=False)
    error_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message = relationship("MessageModel", back_populates="llm_errors")
    category = relationship("CategoryModel")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id = Column(BigInteger, nullable=False, unique=True)
    chat_id = Column(BigInteger, nullable=False, unique=True)
    username = Column(Text, nullable=True)
    first_name = Column(Text, nullable=True)
    role = Column(Text, nullable=False, server_default="user")
    status = Column(Text, nullable=False, server_default="pending")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_seen_at = Column(DateTime(timezone=True), nullable=True)


class DecisionModel(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    model = Column(Text, nullable=False)
    prompt_name = Column(Text, nullable=False, server_default="default")
    prompt_version = Column(Text, nullable=False, server_default="v1")
    passed = Column("pass", Boolean, nullable=False)
    score = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    message = relationship("MessageModel", back_populates="decisions")
    category = relationship("CategoryModel", back_populates="decisions")


class DeliveryOutboxModel(Base):
    __tablename__ = "delivery_outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_name = Column(Text, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    source_message_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=True)
    score = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    group_title = Column(Text, nullable=True)
    group_username = Column(Text, nullable=True)
    payload = Column(Text, nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)


class CategoryAclModel(Base):
    __tablename__ = "category_acl"
    __table_args__ = (
        UniqueConstraint("category_id", "user_id", name="uq_category_acl"),
    )

    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserCategoryDeliveryModel(Base):
    __tablename__ = "user_category_delivery"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_user_category_delivery"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled = Column(Boolean, nullable=False, server_default="false")
    mode = Column(Text, nullable=False, server_default="instant")
    digest_kind = Column(Text, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    daily_time_hhmm = Column(Text, nullable=True)
    timezone = Column(Text, nullable=False, server_default="Europe/Berlin")
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserCategoryChatDeliveryOverrideModel(Base):
    __tablename__ = "user_category_chat_delivery_override"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "category_id",
            "chat_id",
            name="uq_user_category_chat_override",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chat_id = Column(BigInteger, primary_key=True)
    enabled = Column(Boolean, nullable=True)
    mode = Column(Text, nullable=True)
    digest_kind = Column(Text, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    daily_time_hhmm = Column(Text, nullable=True)
    timezone = Column(Text, nullable=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FeedbackMessageModel(Base):
    __tablename__ = "feedback_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
