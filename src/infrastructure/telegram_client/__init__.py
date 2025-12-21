"""Telegram client infrastructure exports."""

from .dialog_service import TelethonDialogService
from .collector_service import TelethonCollectorService

__all__ = [
    "TelethonDialogService",
    "TelethonCollectorService",
]
