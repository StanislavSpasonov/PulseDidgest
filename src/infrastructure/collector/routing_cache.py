"""In-memory routing snapshot cache with periodic refresh."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.application.use_cases.routing_snapshot import (
    GetActiveRoutingSnapshotUseCase,
    RoutingSnapshot,
)


class RoutingSnapshotCache:
    def __init__(
        self,
        use_case: GetActiveRoutingSnapshotUseCase,
        refresh_seconds: int = 30,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._use_case = use_case
        self._refresh_seconds = max(5, refresh_seconds)
        self._logger = logger or logging.getLogger("collector.routing_cache")
        self._snapshot = RoutingSnapshot.empty()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def get_snapshot(self) -> RoutingSnapshot:
        return self._snapshot

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        await self.refresh_once()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def refresh_once(self) -> None:
        snapshot = await asyncio.to_thread(self._use_case.execute)
        self._snapshot = snapshot
        if snapshot.active_chat_ids:
            self._logger.info(
                "Routing refreshed: chats=%s bindings=%s",
                len(snapshot.active_chat_ids),
                snapshot.total_bindings,
            )
        else:
            self._logger.info("Routing refreshed: waiting for bindings")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.refresh_once()
            except Exception as exc:  # pragma: no cover
                self._logger.exception("Routing refresh failed: %s", exc)
            await asyncio.sleep(self._refresh_seconds)
