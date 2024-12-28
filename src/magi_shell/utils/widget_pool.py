# src/magi_shell/utils/widget_pool.py
"""
Widget pooling utilities for MAGI Shell.

Provides efficient widget reuse to improve performance and reduce memory usage
by recycling GTK widgets instead of creating new ones.
"""

from collections import deque
from weakref import WeakKeyDictionary

class WidgetPool:
    """
    Manages a pool of reusable GTK widgets.
    
    Instead of creating and destroying widgets frequently, this class maintains
    a pool of pre-created widgets that can be reused when needed.
    
    Attributes:
        _class (type): Widget class to pool
        _pool (collections.deque): Pool of available widgets
        _active (WeakKeyDictionary): Currently active widgets
    """
    
    def __init__(self, widget_class, size=20):
        """
        Initialize the widget pool.
        
        Args:
            widget_class (type): Class of widget to pool
            size (int): Maximum size of the pool
        """
        self._class = widget_class
        self._pool = deque(maxlen=size)
        self._active = WeakKeyDictionary()
        
        # Pre-create widgets
        for _ in range(size):
            self._pool.append(self._create_widget())
    
    def _create_widget(self):
        """Create a new widget instance."""
        return self._class()
    
    def acquire(self):
        """
        Get a widget from the pool.
        
        Returns:
            A widget instance, either from the pool or newly created
        """
        if self._pool:
            widget = self._pool.pop()
        else:
            widget = self._create_widget()
        self._active[widget] = True
        return widget
    
    def release(self, widget):
        """
        Return a widget to the pool.
        
        Args:
            widget: Widget instance to return to the pool
        """
        if widget in self._active:
            del self._active[widget]
            if len(self._pool) < self._pool.maxlen:
                self._pool.append(widget)
