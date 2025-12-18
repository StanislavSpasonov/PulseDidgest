"""Domain entities exposed for application layer."""

from .message import MessageRecord
from .decision import DecisionRecord

__all__ = ["MessageRecord", "DecisionRecord"]
