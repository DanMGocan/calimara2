from __future__ import annotations

import copy
import os
import threading
import time
from collections import OrderedDict
from typing import Hashable


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class TTLCache:
    def __init__(self, *, ttl_seconds: int, max_entries: int = 256):
        self.ttl_seconds = max(0, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self._lock = threading.Lock()
        self._items: OrderedDict[Hashable, tuple[float, object]] = OrderedDict()

    def get(self, key: Hashable):
        if self.ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return copy.deepcopy(value)

    def set(self, key: Hashable, value) -> None:
        if self.ttl_seconds <= 0:
            return
        now = time.monotonic()
        with self._lock:
            self._items[key] = (now + self.ttl_seconds, copy.deepcopy(value))
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


public_cache = TTLCache(
    ttl_seconds=_env_int("PUBLIC_API_CACHE_TTL_SECONDS", 60),
    max_entries=_env_int("PUBLIC_API_CACHE_MAX_ENTRIES", 256),
)
