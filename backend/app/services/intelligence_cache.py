import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Tuple

class IntelligenceLRUCache:
    """Thread-safe in-memory LRU cache with time-to-live (TTL) expiration."""
    def __init__(self, max_size: int = 500, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict() # key -> (value, expires_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            val, expires_at = self._cache[key]
            if time.time() > expires_at:
                del self._cache[key]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                # Evict oldest item (least recently used)
                self._cache.popitem(last=False)
            self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

# Global singleton cache instances
intelligence_cache = IntelligenceLRUCache(max_size=500, default_ttl=600) # 10 min analysis cache
embedding_cache = IntelligenceLRUCache(max_size=1000, default_ttl=3600)  # 1 hour embedding cache
ranking_snapshot_cache = IntelligenceLRUCache(max_size=500, default_ttl=120) # 2 min pagination snapshot cache
