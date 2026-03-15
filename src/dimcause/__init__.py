"""
Dimcause - Dimcause

AI 上下文管理基础设施
"""

__version__ = "0.1.0"
__author__ = "JoeyOnMars"

from .core.event_index import EventIndex
from .core.models import CodeEntity, Entity, Event, EventType, SemanticEvent
from .utils.config import Config as DimcauseConfig

__all__ = [
    "__version__",
    "Event",
    "SemanticEvent",
    "EventType",
    "EventIndex",
    "Entity",
    "CodeEntity",
    "DimcauseConfig",
]
