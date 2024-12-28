# src/magi_shell/models/__init__.py
"""
MAGI Shell model management components.

Provides management interfaces for various AI models used in MAGI Shell.
"""

from .whisper import WhisperManager, update_whisper_script
from .ollama import OllamaManager
from .voice import BaritoneWrangler

__all__ = [
    'WhisperManager',
    'OllamaManager',
    'BaritoneWrangler',
    'update_whisper_script'
]
