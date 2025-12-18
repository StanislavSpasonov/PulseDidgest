"""Domain entities exposed for application layer."""

from .message import MessageRecord
from .decision import DecisionRecord
from .category_config import PrefilterRule, RuntimeCategory, CategorySyncConfig

__all__ = [
    "MessageRecord",
    "DecisionRecord",
    "PrefilterRule",
    "RuntimeCategory",
    "CategorySyncConfig",
]
