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
    "PendingDecisionInfo",
]
