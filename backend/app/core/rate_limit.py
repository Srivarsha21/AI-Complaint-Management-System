"""Sliding-window rate limiter for sensitive endpoints.

State lives in process memory: limits apply per server process and reset on
restart. That is adequate for a single-instance deployment; a multi-instance
deployment would move this to Redis.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Record an attempt. Returns seconds to wait if over the limit, else None."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(window_seconds - (now - hits[0])) + 1)
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, *, attempts_setting: str = "auth_rate_limit_attempts",
               window_setting: str = "auth_rate_limit_window_seconds"):
    """FastAPI dependency limiting attempts per client IP for one scope.

    Limits default to the auth settings; other scopes can name their own settings.
    """

    def dependency(request: Request) -> None:
        settings = get_settings()
        retry_after = limiter.hit(
            f"{scope}:{client_ip(request)}",
            getattr(settings, attempts_setting),
            getattr(settings, window_setting),
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
