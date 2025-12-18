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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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
    name = Column(Text, nullable=False, unique=True)
    prompt = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, server_default="true")
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
    tg_user_id = Column(BigInteger, nullable=False, unique=True)
    chat_id = Column(BigInteger, nullable=False, unique=True)
    username = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
