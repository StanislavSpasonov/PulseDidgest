"""Telegram client infrastructure exports."""

from .collector_client import TelegramCollectorClient
from .dialog_service import TelethonDialogService

__all__ = [
    "TelegramCollectorClient",
    "TelethonDialogService",
]
