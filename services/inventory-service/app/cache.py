from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

from app.config import settings


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class InventoryReadCache:
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str], CacheEntry] = {}
        self._lock = Lock()

    def get(self, namespace: str, key: str) -> Any | None:
        if not settings.inventory_cache_enabled:
            return None

        composite_key = (namespace, key)
        now = monotonic()
        with self._lock:
            entry = self._entries.get(composite_key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(composite_key, None)
                return None
            return entry.value

    def set(self, namespace: str, key: str, value: Any) -> Any:
        if not settings.inventory_cache_enabled:
            return value

        composite_key = (namespace, key)
        with self._lock:
            self._entries[composite_key] = CacheEntry(
                value=value,
                expires_at=monotonic() + self.ttl_seconds,
            )
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


inventory_read_cache = InventoryReadCache(settings.inventory_cache_ttl_seconds)
