# src/magi_shell/utils/__init__.py
"""
MAGI Shell utility modules.
"""

from .cache import Cache
from .update import UpdateManager
from .config import load_config
from .paths import (
    get_magi_root,
    get_magi_path,
    get_config_path,
    get_bin_path,
    get_whisper_script
)
from .ports import (
    is_port_in_use,
    find_process_using_port,
    release_port
)

__all__ = [
    'Cache',
    'UpdateManager',
    'load_config',
    'get_magi_root',
    'get_magi_path',
    'get_config_path',
    'get_bin_path',
    'get_whisper_script',
    'is_port_in_use',
    'find_process_using_port',
    'release_port'
]
