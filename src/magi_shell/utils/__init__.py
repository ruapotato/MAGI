# src/magi_shell/utils/__init__.py
"""
MAGI Shell utility modules.

This module provides core utilities used throughout the MAGI shell,
including caching, update management, and widget pooling functionality.
"""

from .cache import Cache
from .update import UpdateManager
from .widget_pool import WidgetPool
from .config import load_config

__all__ = [
    'Cache',
    'UpdateManager',
    'WidgetPool',
    'load_config'
]
