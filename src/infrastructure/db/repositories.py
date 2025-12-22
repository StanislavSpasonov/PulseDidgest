"""SQLAlchemy repositories for persistence use cases."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.domain.entities import (
    CategoryGroupBinding,
    DigestGroupInfo,
    DeliveryOutboxItem,
    PendingDecisionInfo,
    PrefilterRule,
    RuntimeCategoryGroup,
    DecisionRecord,
    MessageRecord,
    UserRecord,
)

from .models import (
    CategoryGroupModel,
    CategoryModel,
    DecisionModel,
    DeliveryOutboxModel,
    LLMErrorModel,
    MessageModel,
    SourceGroupModel,
    UserModel,
)


class SQLAlchemyMessageDecisionRepository:
    """Persists messages, decisions, and related metadata using SQLAlchemy."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def save_message_and_decision(
        self, message: MessageRecord, decision: DecisionRecord
    ) -> tuple[str, str]:
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
            return str(db_message.id), str(db_decision.id)
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

    def mark_decision_delivered(self, decision_id: str) -> None:
        session = self._session_factory()
        try:
            stmt = select(DecisionModel).where(DecisionModel.id == uuid.UUID(decision_id))
            db_decision = session.execute(stmt).scalar_one_or_none()
            if db_decision is None:
                return
            db_decision.delivered_at = func.now()
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

    def has_any_categories(self) -> bool:
        session = self._session_factory()
        try:
            return session.query(CategoryModel).first() is not None
        finally:
            session.close()

    def upsert_category(
        self,
        name: str,
        prompt: str,
        debug_enabled: bool,
        prefilter: PrefilterRule,
    ) -> tuple[str, bool]:
        session = self._session_factory()
        try:
            stmt = select(CategoryModel).where(CategoryModel.name == name)
            category = session.execute(stmt).scalar_one_or_none()
            if category is None:
                category = CategoryModel(name=name)
                session.add(category)
            category.prompt = prompt
            category.is_enabled = True
            category.debug_enabled = debug_enabled
            category.prefilter_min_length = prefilter.min_length
            category.prefilter_include_any = prefilter.include_any or None
            category.prefilter_exclude_any = prefilter.exclude_any or None
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

    def sync_category_groups(
        self, category_id: str, bindings: List[CategoryGroupBinding]
    ) -> None:
        session = self._session_factory()
        try:
            stmt = select(CategoryGroupModel).where(
                CategoryGroupModel.category_id == uuid.UUID(category_id)
            )
            existing = {
                str(row.group_id): row for row in session.execute(stmt).scalars().all()
            }
            desired = {binding.group_id for binding in bindings}

            # Remove old bindings
            for group_id in set(existing.keys()) - desired:
                session.delete(existing[group_id])

            # Upsert desired bindings
            for binding in bindings:
                group_uuid = uuid.UUID(binding.group_id)
                link = existing.get(binding.group_id)
                if link is None:
                    link = CategoryGroupModel(
                        category_id=uuid.UUID(category_id),
                        group_id=group_uuid,
                    )
                    session.add(link)
                link.is_enabled = binding.is_enabled
                link.delivery_mode = binding.delivery_mode
                link.delivery_interval_minutes = binding.delivery_interval_minutes
                link.delivery_time_local = binding.delivery_time_local
                link.delivery_tz = binding.delivery_timezone
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def load_runtime_registry(self) -> Dict[int, List[RuntimeCategoryGroup]]:
        session = self._session_factory()
        try:
            stmt = (
                select(CategoryGroupModel, CategoryModel, SourceGroupModel)
                .join(CategoryModel, CategoryModel.id == CategoryGroupModel.category_id)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
                .where(CategoryGroupModel.delivery_mode != "instant")
            )
            mapping: Dict[int, List[RuntimeCategoryGroup]] = {}
            for group_link, category, source_group in session.execute(stmt).all():
                prefilter = PrefilterRule(
                    min_length=category.prefilter_min_length,
                    include_any=(category.prefilter_include_any or []),
                    exclude_any=(category.prefilter_exclude_any or []),
                )
                runtime = RuntimeCategoryGroup(
                    category_id=str(category.id),
                    category_name=category.name,
                    prompt=category.prompt,
                    debug_enabled=bool(category.debug_enabled),
                    prefilter=prefilter,
                    group_id=str(group_link.group_id),
                    chat_id=int(source_group.tg_chat_id),
                    group_title=source_group.title,
                    group_username=source_group.username,
                    delivery_mode=group_link.delivery_mode,
                    delivery_interval_minutes=group_link.delivery_interval_minutes,
                    delivery_time_local=group_link.delivery_time_local,
                    delivery_timezone=group_link.delivery_tz,
                    last_sent_at=group_link.last_sent_at,
                    is_enabled=group_link.is_enabled,
                    category_delivery_mode=category.default_delivery_mode,
                    category_delivery_interval_minutes=category.default_delivery_interval_minutes,
                    category_delivery_time_local=category.default_delivery_time_local,
                    category_delivery_timezone=category.default_delivery_tz,
                    category_delivery_enabled=bool(category.default_delivery_enabled),
                )
                mapping.setdefault(runtime.chat_id, []).append(runtime)
            return mapping
        finally:
            session.close()

    def load_active_routes(self) -> List[RuntimeCategoryGroup]:
        session = self._session_factory()
        try:
            stmt = (
                select(CategoryGroupModel, CategoryModel, SourceGroupModel)
                .join(CategoryModel, CategoryModel.id == CategoryGroupModel.category_id)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
                .where(CategoryGroupModel.is_enabled.is_(True))
                .where(CategoryModel.is_enabled.is_(True))
            )
            routes: List[RuntimeCategoryGroup] = []
            for group_link, category, source_group in session.execute(stmt).all():
                prefilter = PrefilterRule(
                    min_length=category.prefilter_min_length,
                    include_any=(category.prefilter_include_any or []),
                    exclude_any=(category.prefilter_exclude_any or []),
                )
                routes.append(
                    RuntimeCategoryGroup(
                        category_id=str(category.id),
                        category_name=category.name,
                        prompt=category.prompt,
                        debug_enabled=bool(category.debug_enabled),
                        prefilter=prefilter,
                        group_id=str(group_link.group_id),
                        chat_id=int(source_group.tg_chat_id),
                        group_title=source_group.title,
                        group_username=source_group.username,
                        delivery_mode=group_link.delivery_mode,
                        delivery_interval_minutes=group_link.delivery_interval_minutes,
                        delivery_time_local=group_link.delivery_time_local,
                        delivery_timezone=group_link.delivery_tz,
                        last_sent_at=group_link.last_sent_at,
                        is_enabled=group_link.is_enabled,
                        category_delivery_mode=category.default_delivery_mode,
                        category_delivery_interval_minutes=category.default_delivery_interval_minutes,
                        category_delivery_time_local=category.default_delivery_time_local,
                        category_delivery_timezone=category.default_delivery_tz,
                        category_delivery_enabled=bool(category.default_delivery_enabled),
                    )
                )
            return routes
        finally:
            session.close()


class SQLAlchemyDeliveryRepository:
    """Provides data for digest delivery processing."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def fetch_digest_groups(self) -> List[DigestGroupInfo]:
        session = self._session_factory()
        try:
            stmt = (
                select(CategoryGroupModel, CategoryModel, SourceGroupModel)
                .join(CategoryModel, CategoryModel.id == CategoryGroupModel.category_id)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
            )
            groups: List[DigestGroupInfo] = []
            for group_link, category, source_group in session.execute(stmt).all():
                groups.append(
                    DigestGroupInfo(
                        category_id=str(category.id),
                        category_name=category.name,
                        group_id=str(group_link.group_id),
                        chat_id=int(source_group.tg_chat_id),
                        group_title=source_group.title,
                        delivery_mode=group_link.delivery_mode,
                        delivery_interval_minutes=group_link.delivery_interval_minutes,
                        delivery_time_local=group_link.delivery_time_local,
                        delivery_timezone=group_link.delivery_tz,
                        last_sent_at=group_link.last_sent_at,
                        is_enabled=group_link.is_enabled,
                    )
                )
            return groups
        finally:
            session.close()

    def fetch_pending_decisions(
        self, category_id: str, chat_id: int, limit: int
    ) -> List[PendingDecisionInfo]:
        session = self._session_factory()
        try:
            stmt = (
                select(DecisionModel, MessageModel, CategoryModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .join(CategoryModel, DecisionModel.category_id == CategoryModel.id)
                .where(DecisionModel.category_id == uuid.UUID(category_id))
                .where(DecisionModel.delivered_at.is_(None))
                .where(DecisionModel.passed.is_(True))
                .where(MessageModel.source_chat_id == chat_id)
                .order_by(DecisionModel.created_at.asc())
                .limit(limit)
            )
            results: List[PendingDecisionInfo] = []
            for decision, message, category in session.execute(stmt).all():
                results.append(
                    PendingDecisionInfo(
                        decision_id=str(decision.id),
                        category_id=str(category.id),
                        category_name=category.name,
                        message_text=message.text or "",
                        source_chat_id=int(message.source_chat_id),
                        source_message_id=int(message.source_message_id),
                        score=decision.score,
                        reason=decision.reason,
                        created_at=decision.created_at,
                    )
                )
            return results
        finally:
            session.close()

    def fetch_recent_passed_decisions(
        self, category_id: str, chat_id: int, since: datetime, limit: int
    ) -> List[PendingDecisionInfo]:
        session = self._session_factory()
        try:
            stmt = (
                select(DecisionModel, MessageModel, CategoryModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .join(CategoryModel, DecisionModel.category_id == CategoryModel.id)
                .where(DecisionModel.category_id == uuid.UUID(category_id))
                .where(DecisionModel.passed.is_(True))
                .where(MessageModel.source_chat_id == chat_id)
                .where(DecisionModel.created_at >= since)
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            results: List[PendingDecisionInfo] = []
            for decision, message, category in session.execute(stmt).all():
                results.append(
                    PendingDecisionInfo(
                        decision_id=str(decision.id),
                        category_id=str(category.id),
                        category_name=category.name,
                        message_text=message.text or "",
                        source_chat_id=int(message.source_chat_id),
                        source_message_id=int(message.source_message_id),
                        score=decision.score,
                        reason=decision.reason,
                        created_at=decision.created_at,
                    )
                )
            return results
        finally:
            session.close()
    def mark_decisions_delivered(self, decision_ids: List[str]) -> None:
        if not decision_ids:
            return
        session = self._session_factory()
        try:
            for chunk in [decision_ids[i : i + 50] for i in range(0, len(decision_ids), 50)]:
                stmt = (
                    select(DecisionModel)
                    .where(DecisionModel.id.in_([uuid.UUID(d) for d in chunk]))
                )
                for decision in session.execute(stmt).scalars():
                    decision.delivered_at = func.now()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_last_sent(
        self, category_id: str, group_id: str, timestamp
    ) -> None:
        session = self._session_factory()
        try:
            stmt = select(CategoryGroupModel).where(
                CategoryGroupModel.category_id == uuid.UUID(category_id),
                CategoryGroupModel.group_id == uuid.UUID(group_id),
            )
            link = session.execute(stmt).scalar_one_or_none()
            if link is None:
                return
            link.last_sent_at = timestamp
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class SQLAlchemyDeliveryOutboxRepository:
    """Stores delivery outbox items for scheduled sending."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def enqueue(self, item: DeliveryOutboxItem) -> None:
        session = self._session_factory()
        try:
            model = DeliveryOutboxModel(
                id=uuid.UUID(item.id),
                user_id=uuid.UUID(item.user_id) if item.user_id else None,
                decision_id=uuid.UUID(item.decision_id),
                category_id=uuid.UUID(item.category_id),
                category_name=item.category_name,
                chat_id=item.chat_id,
                source_message_id=item.source_message_id,
                message_text=item.message_text,
                score=item.score,
                reason=item.reason,
                group_title=item.group_title,
                group_username=item.group_username,
                payload=item.payload,
                due_at=item.due_at,
                created_at=item.created_at,
                sent_at=item.sent_at,
                last_error=item.last_error,
            )
            session.add(model)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def fetch_due(self, now: datetime, limit: int = 200) -> List[DeliveryOutboxItem]:
        session = self._session_factory()
        try:
            stmt = (
                select(DeliveryOutboxModel)
                .where(DeliveryOutboxModel.sent_at.is_(None))
                .where(DeliveryOutboxModel.due_at <= now)
                .order_by(DeliveryOutboxModel.due_at.asc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                DeliveryOutboxItem(
                    id=str(row.id),
                    user_id=str(row.user_id) if row.user_id else None,
                    decision_id=str(row.decision_id),
                    category_id=str(row.category_id),
                    category_name=row.category_name,
                    chat_id=int(row.chat_id),
                    source_message_id=int(row.source_message_id),
                    message_text=row.message_text,
                    score=row.score,
                    reason=row.reason,
                    group_title=row.group_title,
                    group_username=row.group_username,
                    payload=row.payload,
                    due_at=row.due_at,
                    created_at=row.created_at,
                    sent_at=row.sent_at,
                    last_error=row.last_error,
                )
                for row in rows
            ]
        finally:
            session.close()

    def mark_sent(self, ids: List[str], sent_at: datetime) -> None:
        if not ids:
            return
        session = self._session_factory()
        try:
            stmt = (
                select(DeliveryOutboxModel)
                .where(DeliveryOutboxModel.id.in_([uuid.UUID(i) for i in ids]))
            )
            for row in session.execute(stmt).scalars().all():
                row.sent_at = sent_at
                row.last_error = None
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_error(self, item_id: str, error_text: str) -> None:
        session = self._session_factory()
        try:
            row = session.execute(
                select(DeliveryOutboxModel).where(
                    DeliveryOutboxModel.id == uuid.UUID(item_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return
            row.last_error = error_text
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_errors(self, limit: int = 50) -> List[DeliveryOutboxItem]:
        session = self._session_factory()
        try:
            stmt = (
                select(DeliveryOutboxModel)
                .where(DeliveryOutboxModel.last_error.is_not(None))
                .order_by(DeliveryOutboxModel.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                DeliveryOutboxItem(
                    id=str(row.id),
                    user_id=str(row.user_id) if row.user_id else None,
                    decision_id=str(row.decision_id),
                    category_id=str(row.category_id),
                    category_name=row.category_name,
                    chat_id=int(row.chat_id),
                    source_message_id=int(row.source_message_id),
                    message_text=row.message_text,
                    score=row.score,
                    reason=row.reason,
                    group_title=row.group_title,
                    group_username=row.group_username,
                    payload=row.payload,
                    due_at=row.due_at,
                    created_at=row.created_at,
                    sent_at=row.sent_at,
                    last_error=row.last_error,
                )
                for row in rows
            ]
        finally:
            session.close()
class SQLAlchemyUserRepository:
    """Manages Telegram bot users."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def register_user(self, tg_user_id: int, chat_id: int, username: str | None) -> str:
        session = self._session_factory()
        try:
            stmt = select(UserModel).where(UserModel.tg_user_id == tg_user_id)
            user = session.execute(stmt).scalar_one_or_none()
            if user is None:
                user = UserModel(
                    tg_user_id=tg_user_id,
                    chat_id=chat_id,
                    username=username,
                    is_active=True,
                )
                session.add(user)
            else:
                user.chat_id = chat_id
                user.username = username
                user.is_active = True
            session.commit()
            return str(user.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_active_users(self) -> List[UserRecord]:
        session = self._session_factory()
        try:
            stmt = select(UserModel).where(UserModel.is_active.is_(True))
            users = session.execute(stmt).scalars().all()
            return [
                UserRecord(
                    id=str(user.id),
                    tg_user_id=int(user.tg_user_id),
                    chat_id=int(user.chat_id),
                    username=user.username,
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
                for user in users
            ]
        finally:
            session.close()


class SQLAlchemyAdminRepository:
    """Administrative helpers for the Telegram bot."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Category operations
    def list_categories(self) -> List[CategoryModel]:
        session = self._session_factory()
        try:
            stmt = select(CategoryModel).order_by(CategoryModel.name.asc())
            return session.execute(stmt).scalars().all()
        finally:
            session.close()

    def get_category_by_id(self, category_id: str) -> CategoryModel:
        session = self._session_factory()
        try:
            category = session.execute(
                select(CategoryModel).where(CategoryModel.id == uuid.UUID(category_id))
            ).scalar_one_or_none()
            if category is None:
                raise ValueError("Category not found")
            return category
        finally:
            session.close()

    def get_category_details_by_id(self, category_id: str):
        session = self._session_factory()
        try:
            category = session.execute(
                select(CategoryModel).where(CategoryModel.id == uuid.UUID(category_id))
            ).scalar_one_or_none()
            if category is None:
                raise ValueError("Category not found")
            stmt = (
                select(CategoryGroupModel, SourceGroupModel)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
                .where(CategoryGroupModel.category_id == category.id)
            )
            return category, session.execute(stmt).all()
        finally:
            session.close()

    def create_category(self, name: str) -> None:
        session = self._session_factory()
        try:
            existing = session.execute(
                select(CategoryModel).where(CategoryModel.name == name)
            ).scalar_one_or_none()
            if existing:
                raise ValueError("Category already exists")
            session.add(CategoryModel(name=name, prompt=""))
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def rename_category(self, current_name: str, new_name: str) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, current_name)
            existing = session.execute(
                select(CategoryModel).where(CategoryModel.name == new_name)
            ).scalar_one_or_none()
            if existing and existing.id != category.id:
                raise ValueError("Category already exists")
            category.name = new_name
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_category(self, name: str) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            session.delete(category)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_category_prompt(self, name: str, prompt: str) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            category.prompt = prompt
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_category_debug(self, name: str, enabled: bool) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            category.debug_enabled = enabled
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_category_details(self, name: str):
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            stmt = (
                select(CategoryGroupModel, SourceGroupModel)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
                .where(CategoryGroupModel.category_id == category.id)
            )
            return category, session.execute(stmt).all()
        finally:
            session.close()

    # Group operations
    def list_groups(self) -> List[SourceGroupModel]:
        session = self._session_factory()
        try:
            stmt = select(SourceGroupModel).order_by(SourceGroupModel.created_at.desc())
            return session.execute(stmt).scalars().all()
        finally:
            session.close()

    def register_group(
        self, chat_id: int, title: Optional[str], username: Optional[str] = None
    ) -> None:
        session = self._session_factory()
        try:
            group = session.execute(
                select(SourceGroupModel).where(SourceGroupModel.tg_chat_id == chat_id)
            ).scalar_one_or_none()
            if group is None:
                group = SourceGroupModel(
                    tg_chat_id=chat_id, title=title, username=username
                )
                session.add(group)
            else:
                if title:
                    group.title = title
                if username:
                    group.username = username
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_group(self, chat_id: int) -> None:
        session = self._session_factory()
        try:
            group = session.execute(
                select(SourceGroupModel).where(SourceGroupModel.tg_chat_id == chat_id)
            ).scalar_one_or_none()
            if group is None:
                raise ValueError("Group not found")
            session.delete(group)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def bind_category(self, category_name: str, chat_id: int) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, category_name)
            group = self._get_or_create_group(session, chat_id)
            link = self._get_or_create_link(session, category.id, group.id)
            link.is_enabled = True
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def unbind_category(self, category_name: str, chat_id: int) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, category_name)
            group = self._get_group(session, chat_id)
            link = self._get_link(session, category.id, group.id)
            session.delete(link)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Delivery settings
    def get_delivery_info(self, name: str):
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            stmt = (
                select(CategoryGroupModel, SourceGroupModel)
                .join(SourceGroupModel, SourceGroupModel.id == CategoryGroupModel.group_id)
                .where(CategoryGroupModel.category_id == category.id)
            )
            return session.execute(stmt).all()
        finally:
            session.close()

    def set_delivery(
        self,
        category_name: str,
        chat_id: int,
        mode: str,
        interval_minutes: Optional[int],
        time_local: Optional[str],
        timezone: str,
    ) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, category_name)
            group = self._get_group(session, chat_id)
            link = self._get_link(session, category.id, group.id)
            link.delivery_mode = mode
            link.delivery_interval_minutes = interval_minutes
            link.delivery_time_local = time_local
            link.delivery_tz = timezone
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_delivery_enabled(
        self, category_name: str, chat_id: int, enabled: bool
    ) -> None:
        session = self._session_factory()
        try:
            category = self._get_category(session, category_name)
            group = self._get_group(session, chat_id)
            link = self._get_link(session, category.id, group.id)
            link.is_enabled = enabled
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_delivery_for_category(
        self,
        category_name: str,
        mode: str,
        interval_minutes: Optional[int],
        time_local: Optional[str],
        timezone: str,
        enabled: Optional[bool] = None,
    ) -> int:
        session = self._session_factory()
        try:
            category = self._get_category(session, category_name)
            stmt = select(CategoryGroupModel).where(
                CategoryGroupModel.category_id == category.id
            )
            links = session.execute(stmt).scalars().all()
            for link in links:
                link.delivery_mode = mode
                link.delivery_interval_minutes = interval_minutes
                link.delivery_time_local = time_local
                link.delivery_tz = timezone
                if enabled is not None:
                    link.is_enabled = enabled
            session.commit()
            return len(links)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Reports
    def report_category(
        self, name: str, hours: int, limit: int
    ) -> Tuple[int, int, List[Tuple[DecisionModel, MessageModel]]]:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            since = datetime.utcnow() - timedelta(hours=hours)
            pass_count = session.execute(
                select(func.count())
                .select_from(DecisionModel)
                .where(DecisionModel.category_id == category.id)
                .where(DecisionModel.created_at >= since)
                .where(DecisionModel.passed.is_(True))
            ).scalar_one()
            fail_count = session.execute(
                select(func.count())
                .select_from(DecisionModel)
                .where(DecisionModel.category_id == category.id)
                .where(DecisionModel.created_at >= since)
                .where(DecisionModel.passed.is_(False))
            ).scalar_one()
            recent = (
                select(DecisionModel, MessageModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .where(DecisionModel.category_id == category.id)
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(recent).all()
            return pass_count, fail_count, rows
        finally:
            session.close()

    def report_group(
        self, name: str, chat_id: int, hours: int, limit: int
    ) -> Tuple[int, int, List[Tuple[DecisionModel, MessageModel]]]:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            since = datetime.utcnow() - timedelta(hours=hours)
            pass_count = session.execute(
                select(func.count())
                .select_from(DecisionModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .where(DecisionModel.category_id == category.id)
                .where(MessageModel.source_chat_id == chat_id)
                .where(DecisionModel.created_at >= since)
                .where(DecisionModel.passed.is_(True))
            ).scalar_one()
            fail_count = session.execute(
                select(func.count())
                .select_from(DecisionModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .where(DecisionModel.category_id == category.id)
                .where(MessageModel.source_chat_id == chat_id)
                .where(DecisionModel.created_at >= since)
                .where(DecisionModel.passed.is_(False))
            ).scalar_one()
            recent = (
                select(DecisionModel, MessageModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .where(DecisionModel.category_id == category.id)
                .where(MessageModel.source_chat_id == chat_id)
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(recent).all()
            return pass_count, fail_count, rows
        finally:
            session.close()

    def last_decisions(
        self, name: str, passed: Optional[bool], limit: int
    ) -> List[Tuple[DecisionModel, MessageModel]]:
        session = self._session_factory()
        try:
            category = self._get_category(session, name)
            stmt = (
                select(DecisionModel, MessageModel)
                .join(MessageModel, DecisionModel.message_id == MessageModel.id)
                .where(DecisionModel.category_id == category.id)
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            if passed is True:
                stmt = stmt.where(DecisionModel.passed.is_(True))
            elif passed is False:
                stmt = stmt.where(DecisionModel.passed.is_(False))
            return session.execute(stmt).all()
        finally:
            session.close()

    def list_llm_errors(self, hours: int, limit: int):
        session = self._session_factory()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            stmt = (
                select(LLMErrorModel, CategoryModel)
                .join(CategoryModel, CategoryModel.id == LLMErrorModel.category_id)
                .where(LLMErrorModel.created_at >= since)
                .order_by(LLMErrorModel.created_at.desc())
                .limit(limit)
            )
            return session.execute(stmt).all()
        finally:
            session.close()

    # Helper methods
    def _get_category(self, session: Session, name: str) -> CategoryModel:
        category = session.execute(
            select(CategoryModel).where(CategoryModel.name == name)
        ).scalar_one_or_none()
        if category is None:
            raise ValueError("Category not found")
        return category

    def _get_group(self, session: Session, chat_id: int) -> SourceGroupModel:
        group = session.execute(
            select(SourceGroupModel).where(SourceGroupModel.tg_chat_id == chat_id)
        ).scalar_one_or_none()
        if group is None:
            raise ValueError("Group not found")
        return group

    def _get_or_create_group(
        self, session: Session, chat_id: int
    ) -> SourceGroupModel:
        group = session.execute(
            select(SourceGroupModel).where(SourceGroupModel.tg_chat_id == chat_id)
        ).scalar_one_or_none()
        if group is None:
            group = SourceGroupModel(tg_chat_id=chat_id)
            session.add(group)
            session.flush()
        return group

    def _get_link(
        self, session: Session, category_id: uuid.UUID, group_id: uuid.UUID
    ) -> CategoryGroupModel:
        link = session.execute(
            select(CategoryGroupModel).where(
                CategoryGroupModel.category_id == category_id,
                CategoryGroupModel.group_id == group_id,
            )
        ).scalar_one_or_none()
        if link is None:
            raise ValueError("Binding not found")
        return link

    def _get_or_create_link(
        self, session: Session, category_id: uuid.UUID, group_id: uuid.UUID
    ) -> CategoryGroupModel:
        link = session.execute(
            select(CategoryGroupModel).where(
                CategoryGroupModel.category_id == category_id,
                CategoryGroupModel.group_id == group_id,
            )
        ).scalar_one_or_none()
        if link is None:
            link = CategoryGroupModel(category_id=category_id, group_id=group_id)
            session.add(link)
            session.flush()
        return link
