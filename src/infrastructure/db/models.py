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


class DecisionModel(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    model = Column(Text, nullable=False)
    prompt_name = Column(Text, nullable=False, server_default="default")
    prompt_version = Column(Text, nullable=False, server_default="v1")
    passed = Column("pass", Boolean, nullable=False)
    score = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message = relationship("MessageModel", back_populates="decisions")
