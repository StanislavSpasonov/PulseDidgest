"""Resolve per-user delivery settings and send or enqueue decisions."""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from src.application.services.delivery_policy import resolve_delivery_policy
from src.application.services.user_delivery_policy import resolve_user_delivery_policy
from src.domain.entities import DecisionRecord


class AccessRepository(Protocol):
    def list_active_users_for_category(self, category_id: str):
        ...


class UserDeliveryRepository(Protocol):
    def get_user_category_delivery(self, user_id: str, category_id: str):
        ...

    def get_chat_override(self, user_id: str, category_id: str, chat_id: int):
        ...


class DeliverDecisionUseCase:
    def __init__(
        self,
        access_repo: AccessRepository,
        user_delivery_repo: UserDeliveryRepository,
        instant_delivery_use_case,
        outbox_use_case,
        logger: logging.Logger | None = None,
    ) -> None:
        self._access_repo = access_repo
        self._user_delivery_repo = user_delivery_repo
        self._instant_delivery = instant_delivery_use_case
        self._outbox = outbox_use_case
        self._logger = logger or logging.getLogger("collector.delivery")

    async def deliver(
        self,
        decision_id: str,
        decision: DecisionRecord,
        route,
        message_text: str,
        message_id: int,
    ) -> None:
        base_policy = resolve_delivery_policy(route)
        if not base_policy.enabled:
            return
        users = await asyncio.to_thread(
            self._access_repo.list_active_users_for_category,
            route.category_id,
        )
        if not users:
            self._logger.info("No recipients for category=%s", route.category_name)
            return

        for user in users:
            user_delivery = await asyncio.to_thread(
                self._user_delivery_repo.get_user_category_delivery,
                user.id,
                route.category_id,
            )
            override = await asyncio.to_thread(
                self._user_delivery_repo.get_chat_override,
                user.id,
                route.category_id,
                route.chat_id,
            )
            policy = resolve_user_delivery_policy(
                base_policy,
                user_delivery,
                override,
                user.role == "admin",
            )
            if not policy.enabled:
                continue
            if policy.mode == "instant" and self._instant_delivery:
                await self._instant_delivery.deliver(
                    decision_id,
                    decision,
                    route.category_name,
                    message_text,
                    route.chat_id,
                    message_id,
                    route.group_title,
                    route.group_username,
                    recipient_chat_id=user.chat_id,
                    mark_delivered=False,
                )
            elif policy.mode == "digest" and self._outbox:
                self._outbox.enqueue(
                    decision,
                    message_text,
                    route,
                    policy,
                    decision_id,
                    message_id,
                    user_id=user.id,
                )
