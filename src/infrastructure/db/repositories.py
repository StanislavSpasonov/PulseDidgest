"""SQLAlchemy repositories for persisting messages and decisions."""
from __future__ import annotations

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities import DecisionRecord, MessageRecord

from .models import DecisionModel, MessageModel


class SQLAlchemyMessageDecisionRepository:
    """Persists messages and related decisions using SQLAlchemy."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def save_message_and_decision(
        self, message: MessageRecord, decision: DecisionRecord
    ) -> None:
        session = self._session_factory()
        try:
            db_message = self._get_or_create_message(session, message)
            db_decision = DecisionModel(
                message_id=db_message.id,
                model=decision.model,
                prompt_name=decision.prompt_name,
                prompt_version=decision.prompt_version,
                passed=decision.passed,
                score=decision.score,
                reason=decision.reason,
            )
            session.add(db_decision)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _get_or_create_message(
        self, session: Session, message: MessageRecord
    ) -> MessageModel:
        stmt = select(MessageModel).where(
            MessageModel.source_chat_id == message.source_chat_id,
            MessageModel.source_message_id == message.source_message_id,
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            return existing

        db_message = MessageModel(
            source_chat_id=message.source_chat_id,
            source_message_id=message.source_message_id,
            date=message.date,
            text=message.text,
        )
        session.add(db_message)
        session.flush()
        return db_message
