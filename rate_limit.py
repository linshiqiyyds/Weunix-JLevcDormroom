from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    min_interval: float
    _last_call: float = field(default=0.0, init=False)

    def wait(self) -> float:
        now = time.monotonic()
        elapsed = now - self._last_call
        delay = max(0.0, self.min_interval - elapsed)
        if delay:
            time.sleep(delay)
        self._last_call = time.monotonic()
        return delay

    def ready(self) -> bool:
        return time.monotonic() - self._last_call >= self.min_interval


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        if rate <= 0:
            raise ValueError("rate must be positive")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
