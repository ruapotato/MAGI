# src/magi_shell/widgets/__init__.py
"""
MAGI Shell widget components.

This module provides the GUI widgets used throughout the MAGI shell interface,
including workspace management, window management, system monitoring, and
voice interaction components.
"""

from .voice import WhisperingEarButton, VoiceInputButton
from .workspace import WorkspaceSwitcher
from .window import WindowList
from .system import SystemMonitor

__all__ = [
    'WhisperingEarButton',
    'VoiceInputButton',
    'WorkspaceSwitcher',
    'WindowList',
    'SystemMonitor'
]
