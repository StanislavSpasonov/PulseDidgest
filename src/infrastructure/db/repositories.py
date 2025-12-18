"""SQLAlchemy repositories for persisting messages and decisions."""
from __future__ import annotations

import uuid
from typing import Callable, List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.domain.entities import DecisionRecord, MessageRecord

from .models import (
    CategoryGroupModel,
    CategoryModel,
    DecisionModel,
    LLMErrorModel,
    MessageModel,
    SourceGroupModel,
)


class SQLAlchemyMessageDecisionRepository:
    """Persists messages and related decisions using SQLAlchemy."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def save_message_and_decision(
        self, message: MessageRecord, decision: DecisionRecord
    ) -> str:
        session = self._session_factory()
        try:
            db_message = self._get_or_create_message(session, message)
            db_decision = DecisionModel(
                message_id=db_message.id,
                category_id=uuid.UUID(decision.category_id),
                model=decision.model,
                prompt_name=decision.prompt_name,
                prompt_version=decision.prompt_version,
                passed=decision.passed,
                score=decision.score,
                reason=decision.reason,
            )
            session.add(db_decision)
            session.commit()
            return str(db_message.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ensure_message(self, message: MessageRecord) -> str:
        session = self._session_factory()
        try:
            db_message = self._get_or_create_message(session, message)
            session.commit()
            return str(db_message.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_llm_error(
        self, message: MessageRecord, category_id: str, error_code: str, error_text: str
    ) -> None:
        session = self._session_factory()
        try:
            db_message = self._get_or_create_message(session, message)
            session.add(
                LLMErrorModel(
                    message_id=db_message.id,
                    category_id=uuid.UUID(category_id),
                    error_code=error_code,
                    error_text=error_text,
                )
            )
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


class SQLAlchemyCategoryRepository:
    """Handles category/group synchronization and queries."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def upsert_category(
        self, name: str, prompt: str, is_enabled: bool = True
    ) -> tuple[str, bool]:
        session = self._session_factory()
        try:
            stmt = select(CategoryModel).where(CategoryModel.name == name)
            category = session.execute(stmt).scalar_one_or_none()
            if category is None:
                category = CategoryModel(name=name, prompt=prompt, is_enabled=is_enabled)
                session.add(category)
            else:
                category.prompt = prompt
                category.is_enabled = is_enabled
            session.commit()
            return str(category.id), bool(category.is_enabled)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_source_group(
        self, tg_chat_id: int, title: str | None = None
    ) -> str:
        session = self._session_factory()
        try:
            stmt = select(SourceGroupModel).where(
                SourceGroupModel.tg_chat_id == tg_chat_id
            )
            group = session.execute(stmt).scalar_one_or_none()
            if group is None:
                group = SourceGroupModel(tg_chat_id=tg_chat_id, title=title)
                session.add(group)
            else:
                if title:
                    group.title = title
            session.commit()
            return str(group.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def sync_category_groups(self, category_id: str, group_ids: List[str]) -> None:
        session = self._session_factory()
        try:
            stmt = select(CategoryGroupModel.group_id).where(
                CategoryGroupModel.category_id == uuid.UUID(category_id)
            )
            existing = {str(row[0]) for row in session.execute(stmt).all()}
            desired = set(group_ids)

            to_add = desired - existing
            to_remove = existing - desired

            for group_id in to_add:
                session.add(
                    CategoryGroupModel(
                        category_id=uuid.UUID(category_id),
                        group_id=uuid.UUID(group_id),
                    )
                )

            if to_remove:
                session.execute(
                    delete(CategoryGroupModel)
                    .where(CategoryGroupModel.category_id == uuid.UUID(category_id))
                    .where(CategoryGroupModel.group_id.in_([uuid.UUID(g) for g in to_remove]))
                )

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
