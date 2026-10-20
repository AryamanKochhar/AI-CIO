"""Bounded, atomic public-market-data cache with per-key single flight."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable


class PublicDataCache:
    """Thread-safe cache; failures never replace an older successful response.

    The lock is intentionally process-local. Atomic os.replace still prevents
    partially written JSON when more than one API worker refreshes the cache.
    A finite number of striped locks bounds memory independently of key count.
    """

    _locks = [threading.RLock() for _ in range(64)]

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    @contextmanager
    def locked(self, key: str):
        digest = hashlib.sha256(str(self._path(key)).encode()).digest()
        with self._locks[int.from_bytes(digest[:2], "big") % len(self._locks)]:
            yield

    def read(self, key: str) -> dict | None:
        try:
            path = self._path(key)
            if path.stat().st_size > 24_000_000:
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) and value.get("key") == key else None
        except (OSError, ValueError, TypeError):
            return None

    def write(self, key: str, payload, *, fetched_at: float | None = None) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        when = time.time() if fetched_at is None else fetched_at
        record = {"key": key, "fetched_at": when,
                  "retrieved_at": datetime.fromtimestamp(when, timezone.utc).isoformat(),
                  "payload": payload}
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > 24_000_000:
            raise ValueError("Market data exceeds the cache size bound")
        path = self._path(key)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                handle.write(encoded)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        return record

    def get(self, key: str, ttl: float, loader: Callable, *, max_stale: float = 0) -> dict:
        with self.locked(key):
            cached = self.read(key)
            age = time.time() - cached["fetched_at"] if cached else float("inf")
            if cached and 0 <= age < ttl:
                return {**cached, "cache_status": "hit", "stale": False}
            try:
                value = loader()
                return {**self.write(key, value), "cache_status": "refreshed", "stale": False}
            except Exception:
                if cached and 0 <= age <= ttl + max_stale:
                    return {**cached, "cache_status": "stale_on_error", "stale": True}
                raise
