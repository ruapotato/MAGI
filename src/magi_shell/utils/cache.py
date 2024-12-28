# src/magi_shell/utils/cache.py
"""
Caching utilities for MAGI Shell.

Provides a simple time-based caching mechanism to store frequently accessed data
and reduce redundant computations or system calls.
"""

import time

class Cache:
    """
    Time-based cache implementation for storing temporary data.
    
    Attributes:
        _cache (dict): Storage for cached values
        _timestamps (dict): Timestamps for cache entries
        _timeout (int): Cache timeout in milliseconds
    """
    
    def __init__(self, timeout=5000):
        self._cache = {}
        self._timestamps = {}
        self._timeout = timeout
    
    def get(self, key):
        """
        Retrieve a value from the cache if it hasn't expired.
        
        Args:
            key: Cache key to lookup
            
        Returns:
            The cached value if valid, None otherwise
        """
        if key in self._cache:
            timestamp = self._timestamps[key]
            if time.monotonic() * 1000 - timestamp < self._timeout:
                return self._cache[key]
            del self._cache[key]
            del self._timestamps[key]
        return None
    
    def set(self, key, value):
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value
        self._timestamps[key] = time.monotonic() * 1000
