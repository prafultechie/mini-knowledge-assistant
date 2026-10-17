import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from app.config import settings


class InMemoryRateLimiter:
    """Per-process demo limiter. Use Redis for consistent limits across replicas."""
    def __init__(self) -> None:
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        events = self.requests[key]
        cutoff = now - settings.rate_limit_window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= settings.rate_limit_requests:
            retry_after = max(1, int(settings.rate_limit_window_seconds - (now - events[0])))
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again shortly.", headers={"Retry-After": str(retry_after)})
        events.append(now)


limiter = InMemoryRateLimiter()
