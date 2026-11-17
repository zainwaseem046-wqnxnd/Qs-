"""Fixed-window rate limiter backed by Redis, with an in-process fallback for tests/dev.

Used for authentication endpoints (credential stuffing defence). Edge/WAF rate limiting is a separate
infrastructure control documented in docs/SECURITY.md.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

from app.core.config import get_settings
from app.core.errors import RateLimited

logger = logging.getLogger("qs.ratelimit")


class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = defaultdict(int)

    def incr(self, key: str, window_seconds: int) -> int:
        with self._lock:
            self._counts[key] += 1
            return self._counts[key]

    def clear(self) -> None:
        with self._lock:
            self._counts.clear()


class _RedisBackend:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)

    def incr(self, key: str, window_seconds: int) -> int:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        count, _ = pipe.execute()
        return int(count)


_memory = _MemoryBackend()
_backend: _RedisBackend | _MemoryBackend | None = None


def _get_backend() -> _RedisBackend | _MemoryBackend:
    global _backend
    if _backend is None:
        settings = get_settings()
        if settings.redis_url and settings.environment != "test":
            _backend = _RedisBackend(settings.redis_url)
        else:
            _backend = _memory
    return _backend


def reset_rate_limits() -> None:
    _memory.clear()


def check_rate_limit(bucket: str, identifier: str, limit: int, window_seconds: int = 60) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    window = int(time.time() // window_seconds)
    key = f"rl:{bucket}:{identifier}:{window}"
    try:
        count = _get_backend().incr(key, window_seconds)
    except Exception:  # Redis unavailable: degrade to in-process limiting rather than fail open entirely
        logger.warning("Rate limit backend unavailable; using in-process fallback")
        count = _memory.incr(key, window_seconds)
    if count > limit:
        raise RateLimited("Too many attempts. Please wait a minute and try again.")
