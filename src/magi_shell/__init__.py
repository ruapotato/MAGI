# src/magi_shell/__init__.py
"""
MAGI Shell - Where Pixels Meet Philosophy

A modern Linux desktop shell built with GTK4 and Python, featuring
workspace management, window management, system monitoring, and
voice interaction capabilities.

The shell provides:
- Dynamic workspace management
- Window management and switching
- System resource monitoring
- Voice input and control
- AI assistant integration
"""

from .core import MAGIApplication, main

__version__ = '0.0.5'
__author__ = 'David Hamner'

# Expose the main entry point
if __name__ == "__main__":
    main()
