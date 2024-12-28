# src/magi_shell/monitors/__init__.py
"""
MAGI Shell monitoring components.
"""

from .status import ServiceStatusDisplay
from .window import ModelManager
from .application import ModelManagerApplication, main

__all__ = [
    'ModelManagerApplication',
    'ModelManager',
    'ServiceStatusDisplay',
    'main'
]
