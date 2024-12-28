# src/magi_shell/utils/update.py
"""
Update management utilities for MAGI Shell.

This module provides the UpdateManager class which handles scheduling and processing 
of UI updates in an efficient batched manner.
"""

import time
from gi.repository import GLib

class UpdateManager:
    """
    Manages scheduled updates for the MAGI Shell interface.
    
    The UpdateManager coordinates updates across different components of the interface,
    batching them together for efficiency and preventing redundant updates.
    
    Attributes:
        _updates (dict): Stores update callbacks and their intervals
        _pending (set): Set of pending update names
        _last_update (dict): Timestamps of last updates
        _batch_id (int): Current batch process ID
    """
    
    def __init__(self):
        self._updates = {}
        self._pending = set()
        self._last_update = {}
        self._batch_id = None
    
    def schedule(self, name, callback, interval, priority=GLib.PRIORITY_DEFAULT):
        """
        Schedule an update to be processed in the next batch.
        
        Args:
            name (str): Unique identifier for this update
            callback (callable): Function to be called for the update
            interval (int): Minimum time between updates in milliseconds
            priority (int): GLib priority level for the update
        """
        current_time = time.monotonic() * 1000
        last_time = self._last_update.get(name, 0)
        
        if current_time - last_time < interval:
            return
        
        self._pending.add(name)
        self._updates[name] = (callback, interval)
        
        if not self._batch_id:
            self._batch_id = GLib.timeout_add(
                interval // 10,  # Process updates at 1/10th the interval
                self._process_updates
            )
    
    def _process_updates(self):
        """Process all pending updates in the current batch."""
        current_time = time.monotonic() * 1000
        processed = set()
        
        for name in list(self._pending):
            if name in self._updates:
                callback, interval = self._updates[name]
                last_time = self._last_update.get(name, 0)
                
                if current_time - last_time >= interval:
                    try:
                        callback()
                        self._last_update[name] = current_time
                        processed.add(name)
                    except Exception as e:
                        print(f"Update failed ({name}): {e}")
        
        self._pending -= processed
        self._batch_id = None
        return False
