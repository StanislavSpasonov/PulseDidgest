"""Domain entities exposed for application layer."""

from .message import MessageRecord
from .decision import DecisionRecord
from .category_config import (
    PrefilterRule,
    RuntimeCategory,
    RuntimeCategoryGroup,
    CategorySyncConfig,
    GroupSyncConfig,
    DeliveryConfig,
    CategoryGroupBinding,
)
from .user import UserRecord
from .delivery import DigestGroupInfo, PendingDecisionInfo
from .delivery_outbox import DeliveryOutboxItem
from .telegram_chat import TelegramChatInfo

__all__ = [
    "MessageRecord",
    "DecisionRecord",
    "PrefilterRule",
    "RuntimeCategory",
    "RuntimeCategoryGroup",
    "CategorySyncConfig",
    "GroupSyncConfig",
    "DeliveryConfig",
    "CategoryGroupBinding",
    "UserRecord",
    "DigestGroupInfo",
    "DeliveryOutboxItem",
    "PendingDecisionInfo",
    "TelegramChatInfo",
]
