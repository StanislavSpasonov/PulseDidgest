"""Background delivery engine for digest schedules."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

from src.domain.entities import DigestGroupInfo, PendingDecisionInfo


class DigestRepositoryProtocol:
    def fetch_digest_groups(self) -> List[DigestGroupInfo]:
        raise NotImplementedError

    def fetch_pending_decisions(
        self, category_id: str, chat_id: int, limit: int
    ) -> List[PendingDecisionInfo]:
        raise NotImplementedError

    def mark_decisions_delivered(self, decision_ids: List[str]) -> None:
        raise NotImplementedError

    def update_last_sent(
        self, category_id: str, group_id: str, timestamp: datetime
    ) -> None:
        raise NotImplementedError


class DigestDeliveryEngine:
    """Runs periodic tasks that send digest messages based on delivery_mode."""

    def __init__(
        self,
        repository: DigestRepositoryProtocol,
        notifier,
        tick_seconds: int = 60,
        max_decisions: int = 50,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._repo = repository
        self._notifier = notifier
        self._tick_seconds = max(15, tick_seconds)
        self._max_decisions = max_decisions
        self._logger = logger or logging.getLogger("collector.digest")
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:  # pragma: no cover - normal flow
            pass

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._process_tick()
            except Exception as exc:  # pragma: no cover
                self._logger.exception("Digest tick failed: %s", exc)
            await asyncio.sleep(self._tick_seconds)

    async def _process_tick(self) -> None:
        groups = await asyncio.to_thread(self._repo.fetch_digest_groups)
        if not groups:
            return
        now_utc = datetime.now(timezone.utc)
        for group in groups:
            if not group.is_enabled:
                continue
            if group.delivery_mode == "instant":
                continue
            if not self._should_send(group, now_utc):
                continue
            decisions = await asyncio.to_thread(
                self._repo.fetch_pending_decisions,
                group.category_id,
                group.chat_id,
                self._max_decisions,
            )
            if not decisions:
                continue
            payload = self._build_digest_message(group, decisions)
            delivered = await self._notifier.broadcast(payload)
            if delivered:
                ids = [d.decision_id for d in decisions]
                await asyncio.to_thread(self._repo.mark_decisions_delivered, ids)
                await asyncio.to_thread(
                    self._repo.update_last_sent,
                    group.category_id,
                    group.group_id,
                    now_utc,
                )

    def _should_send(self, group: DigestGroupInfo, now_utc: datetime) -> bool:
        last_sent = group.last_sent_at
        if group.delivery_mode == "hourly":
            return last_sent is None or now_utc - last_sent >= timedelta(hours=1)
        if group.delivery_mode == "interval":
            if not group.delivery_interval_minutes:
                return False
            delta = timedelta(minutes=group.delivery_interval_minutes)
            return last_sent is None or now_utc - last_sent >= delta
        if group.delivery_mode == "daily":
            if not group.delivery_time_local:
                return False
            try:
                hour, minute = [int(part) for part in group.delivery_time_local.split(":", 1)]
            except ValueError:
                return False
            try:
                tz = ZoneInfo(group.delivery_timezone)
            except Exception:
                tz = ZoneInfo("UTC")
            local_now = now_utc.astimezone(tz)
            target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if local_now < target:
                return False
            if last_sent is None:
                return True
            last_local = last_sent.astimezone(tz)
            return last_local.date() < local_now.date()
        return False

    def _build_digest_message(
        self, group: DigestGroupInfo, decisions: Iterable[PendingDecisionInfo]
    ) -> str:
        header = (
            f"[{group.category_name}] Digest for chat {group.group_title or group.chat_id}\n"
        )
        lines = [header]
        for idx, decision in enumerate(decisions, start=1):
            text = (decision.message_text or "").strip().replace("\n", " ")
            snippet = text[:400] + ("…" if len(text) > 400 else "")
            lines.append(
                f"{idx}. Score={decision.score:.2f} Reason={decision.reason}\n   {snippet}"
            )
        payload = "\n\n".join(lines)
        return payload[:3500]
