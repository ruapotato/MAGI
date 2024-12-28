# src/magi_shell/utils/paths.py
"""
Path utilities for MAGI Shell.
"""

from pathlib import Path
import os

def get_magi_root():
    """Get the MAGI root directory."""
    return Path(__file__).parent.parent.parent.parent

def get_src_path():
    """Get the src directory."""
    return get_magi_root() / 'src'

def get_utils_path():
    """Get the utils directory containing whisper and voice servers."""
    return get_src_path() / 'utils'

def get_config_path():
    """Get the MAGI configuration directory."""
    return Path(os.path.expanduser("~/.config/magi"))

def get_magi_path():
    """Get the MAGI source directory."""
    return get_magi_root() / 'src' / 'magi_shell'

def get_bin_path():
    """Get the MAGI bin directory."""
    return get_magi_root() / 'bin'

def get_whisper_script():
    """Get the path to the Whisper server script."""
    return get_utils_path() / 'whisper_server.py'

def get_voice_script():
    """Get the path to the voice server script."""
    return get_utils_path() / 'voice.py'

__all__ = [
    'get_magi_root',
    'get_src_path',
    'get_utils_path',
    'get_config_path',
    'get_bin_path',
    'get_whisper_script',
    'get_voice_script'
]
