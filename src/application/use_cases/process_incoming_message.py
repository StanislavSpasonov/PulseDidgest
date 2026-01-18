"""Use case for processing incoming Telegram messages with routing snapshot."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from src.application.services.prefilter import should_run_llm
from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)
from src.application.use_cases.deliver_decision import DeliverDecisionUseCase
from src.application.services.delivery_policy import resolve_delivery_policy
from src.application.use_cases.routing_snapshot import RoutingSnapshot
from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.domain.entities import DecisionRecord, MessageRecord


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: int
    message_id: int
    date: datetime
    text: str
    raw_meta: dict[str, Any]


class CooldownProtocol(Protocol):
    def in_cooldown(self) -> bool:
        ...

    def activate(self) -> None:
        ...

    def remaining_seconds(self) -> int:
        ...


class AdminNotifier(Protocol):
    async def notify_admin(self, text: str) -> None:
        ...


class ProcessIncomingMessageUseCase:
    def __init__(
        self,
        filter_use_case: FilterMessageWithGeminiUseCase,
        store_use_case: StoreMessageAndDecisionUseCase,
        logger: logging.Logger | None = None,
        instant_delivery_use_case=None,
        outbox_use_case: EnqueueDeliveryOutboxUseCase | None = None,
        deliver_decision_use_case: DeliverDecisionUseCase | None = None,
        notifier: AdminNotifier | None = None,
        debug_throttle=None,
        cooldown: CooldownProtocol | None = None,
    ) -> None:
        self._filter = filter_use_case
        self._store = store_use_case
        self._instant_delivery = instant_delivery_use_case
        self._outbox = outbox_use_case
        self._deliver_decision = deliver_decision_use_case
        self._notifier = notifier
        self._debug_throttle = debug_throttle
        self._cooldown = cooldown
        self._logger = logger or logging.getLogger("collector.process_message")

    async def handle(self, message: IncomingMessage, snapshot: RoutingSnapshot) -> None:
        if not message.text.strip():
            self._logger.debug(
                "Skip empty message chat=%s message_id=%s",
                message.chat_id,
                message.message_id,
            )
            return

        if message.chat_id not in snapshot.active_chat_ids:
            self._logger.debug(
                "Chat %s is not active (bindings=%s)",
                message.chat_id,
                snapshot.total_bindings,
            )
            return

        routes = snapshot.routes.get(message.chat_id, [])
        if not routes:
            self._logger.debug("No routes for chat %s", message.chat_id)
            return

        message_record = MessageRecord(
            source_chat_id=message.chat_id,
            source_message_id=message.message_id,
            date=message.date,
            text=message.text,
        )
        await self._store.ensure_message(message_record)

        for route in routes:
            should_run, reason = should_run_llm(message.text, route.prefilter)
            if not should_run:
                self._logger.info(
                    "Prefilter skipped category=%s reason=%s",
                    route.category_name,
                    reason,
                )
                continue

            if self._cooldown and self._cooldown.in_cooldown():
                self._logger.warning(
                    "Cooldown active (%ss remaining); skipping LLM for category=%s",
                    self._cooldown.remaining_seconds(),
                    route.category_name,
                )
                continue

            try:
                decision = await self._filter.classify(
                    message_text=message.text,
                    category_name=route.category_name,
                    category_prompt=route.prompt,
                )
            except Exception as exc:
                error_code = exc.__class__.__name__
                error_text = str(exc)
                if self._cooldown and error_code == "ResourceExhausted":
                    self._logger.warning(
                        "LLM quota exhausted for category=%s: %s",
                        route.category_name,
                        error_text,
                    )
                    self._cooldown.activate()
                    await self._notify_llm_limit(
                        category_name=route.category_name,
                        error_code=error_code,
                        error_text=error_text,
                    )
                elif self._is_llm_limit_error(error_code, error_text):
                    await self._notify_llm_limit(
                        category_name=route.category_name,
                        error_code=error_code,
                        error_text=error_text,
                    )
                else:
                    self._logger.error(
                        "LLM classification failed for category=%s: %s",
                        route.category_name,
                        error_text,
                    )
                await self._store.record_error(
                    message_record,
                    route.category_id,
                    error_code,
                    error_text,
                )
                continue

            decision_record = DecisionRecord(
                category_id=route.category_id,
                model=decision.model,
                prompt_name=decision.prompt_name,
                prompt_version=decision.prompt_version,
                passed=decision.passed,
                score=decision.score,
                reason=decision.reason,
            )
            saved = await self._store.handle(message_record, decision_record)
            if not saved:
                continue
            _, decision_db_id = saved

            if decision_record.passed:
                if self._deliver_decision:
                    await self._deliver_decision.deliver(
                        decision_db_id,
                        decision_record,
                        route,
                        message.text,
                        message.message_id,
                    )
                elif self._instant_delivery or self._outbox:
                    policy = resolve_delivery_policy(route)
                    if not policy.enabled:
                        continue
                    if policy.mode == "instant" and self._instant_delivery:
                        await self._instant_delivery.deliver(
                            decision_db_id,
                            decision_record,
                            route.category_name,
                            message.text,
                            message.chat_id,
                            message.message_id,
                            route.group_title,
                            route.group_username,
                        )
                    elif policy.mode == "digest" and self._outbox:
                        self._outbox.enqueue(
                            decision_record,
                            message.text,
                            route,
                            policy,
                            decision_db_id,
                            message.message_id,
                        )
                else:
                    self._logger.warning(
                        "Delivery use case missing; instant=%s outbox=%s",
                        bool(self._instant_delivery),
                        bool(self._outbox),
                    )

            if self._notifier and route.debug_enabled and self._debug_throttle:
                allow, warn = self._debug_throttle.check(route.category_id)
                if allow:
                    snippet = message.text.strip()[:400]
                    debug_text = (
                        f"[DEBUG {route.category_name}] pass={decision_record.passed}"
                        f" score={decision_record.score:.2f}\n"
                        f"Reason: {decision_record.reason}\n"
                        f"Chat: {route.chat_id}\n"
                        f"{snippet}"
                    )
                    await self._notifier.notify_admin(debug_text)
                elif warn:
                    await self._notifier.notify_admin(
                        f"[DEBUG {route.category_name}] too many events, throttling"
                    )

    def _is_llm_limit_error(self, error_code: str, error_text: str) -> bool:
        lowered = error_text.lower()
        return (
            error_code == "ResourceExhausted"
            or "quota" in lowered
            or "rate limit" in lowered
            or "rate-limit" in lowered
            or "429" in lowered
            or "resource_exhausted" in lowered
        )

    def _extract_retry_seconds(self, error_text: str) -> int | None:
        match = re.search(r"retry in ([0-9.]+)s", error_text, re.IGNORECASE)
        if match:
            try:
                return int(float(match.group(1)))
            except ValueError:
                return None
        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    async def _notify_llm_limit(
        self,
        category_name: str,
        error_code: str,
        error_text: str,
    ) -> None:
        if not self._notifier:
            return
        retry_seconds = self._extract_retry_seconds(error_text)
        cooldown_seconds = self._cooldown.remaining_seconds() if self._cooldown else 0
        limit_type = "quota" if "quota" in error_text.lower() else "rate"
        code_label = "429" if "429" in error_text else error_code
        message = (
            f"⚠️ LLM лимит/квота ({code_label}). "
            f"Категория: {category_name}. "
            f"Тип: {limit_type}."
        )
        if retry_seconds is not None:
            message += f" Retry через: {retry_seconds}с."
        if cooldown_seconds:
            message += f" Cooldown: {cooldown_seconds}с."
        short_error = error_text.strip().replace("\n", " ")
        if len(short_error) > 200:
            short_error = short_error[:200] + "..."
        message += f" Сообщение: {short_error}"
        await self._notifier.notify_admin(message)
