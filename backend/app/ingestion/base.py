"""
Base abstractions for all platform collectors.

Provides:
  - RateLimiter      sliding-window token bucket backed by Redis
  - CircuitBreaker   open/half-open/closed FSM to shed load on failing APIs
  - IngestionState   Redis-backed key-value checkpoint store per collector
  - BaseCollector    abstract class every platform collector inherits
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.post import Platform, PostIngest

log = structlog.get_logger()


# ──────────────────────────────────────────────────────────────────────────────
# Rate limiter — sliding window using a Redis sorted set
# ──────────────────────────────────────────────────────────────────────────────

class RateLimitExceeded(Exception):
    """Raised when the caller must back off."""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded; retry after {retry_after:.1f}s")


class RateLimiter:
    """
    Sliding-window rate limiter.

    Tracks call timestamps in a Redis sorted set keyed by
    `rl:{namespace}`.  Each call adds an entry; entries older than
    `window_seconds` are pruned before the count check.
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        namespace: str,
        max_calls: int,
        window_seconds: int,
    ) -> None:
        self._redis = redis
        self._key = f"rl:{namespace}"
        self._max = max_calls
        self._window = window_seconds

    async def acquire(self) -> None:
        """
        Claim one call slot.  Blocks (with asyncio.sleep) up to one full
        window if the limit is already reached; raises RateLimitExceeded
        if still over after waiting.
        """
        now = time.time()
        cutoff = now - self._window

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(self._key, "-inf", cutoff)
            pipe.zcard(self._key)
            _, count = await pipe.execute()

        if count >= self._max:
            # Oldest entry tells us when the window clears.
            oldest = await self._redis.zrange(self._key, 0, 0, withscores=True)
            if oldest:
                retry_after = self._window - (now - oldest[0][1])
                retry_after = max(0.1, retry_after)
            else:
                retry_after = self._window
            raise RateLimitExceeded(retry_after)

        member = f"{now:.6f}-{asyncio.get_event_loop().time()}"
        await self._redis.zadd(self._key, {member: now})
        await self._redis.expire(self._key, self._window * 2)

    async def wait_and_acquire(self) -> None:
        """Like acquire() but sleeps instead of raising."""
        while True:
            try:
                await self.acquire()
                return
            except RateLimitExceeded as exc:
                log.debug("Rate limit hit, sleeping", retry_after=exc.retry_after)
                await asyncio.sleep(exc.retry_after)

    async def remaining(self) -> int:
        now = time.time()
        cutoff = now - self._window
        await self._redis.zremrangebyscore(self._key, "-inf", cutoff)
        count = await self._redis.zcard(self._key)
        return max(0, self._max - count)


# ──────────────────────────────────────────────────────────────────────────────
# Circuit breaker — prevents hammering a failing API
# ──────────────────────────────────────────────────────────────────────────────

class CBState(str, Enum):
    CLOSED = "closed"       # Normal; calls flow through.
    OPEN = "open"           # API is broken; calls are rejected.
    HALF_OPEN = "half_open" # Probe attempt to see if API recovered.


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    """
    Three-state FSM stored in Redis so multiple processes share state.

    Keys:
      cb:{name}:state        — CBState string
      cb:{name}:failures     — consecutive failure count
      cb:{name}:opened_at    — unix timestamp of last open event
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 120,
    ) -> None:
        self._redis = redis
        self._name = name
        self._threshold = failure_threshold
        self._recovery = recovery_timeout

    async def state(self) -> CBState:
        raw = await self._redis.get(f"cb:{self._name}:state")
        if raw is None:
            return CBState.CLOSED
        s = CBState(raw.decode())
        if s == CBState.OPEN:
            opened_at = await self._redis.get(f"cb:{self._name}:opened_at")
            if opened_at and time.time() - float(opened_at) > self._recovery:
                await self._set_state(CBState.HALF_OPEN)
                return CBState.HALF_OPEN
        return s

    async def before_call(self) -> None:
        s = await self.state()
        if s == CBState.OPEN:
            raise CircuitBreakerOpen(f"Circuit {self._name!r} is OPEN")

    async def on_success(self) -> None:
        await self._redis.set(f"cb:{self._name}:failures", 0)
        await self._set_state(CBState.CLOSED)

    async def on_failure(self) -> None:
        failures = await self._redis.incr(f"cb:{self._name}:failures")
        log.warning("Circuit breaker failure", name=self._name, failures=failures)
        if failures >= self._threshold:
            await self._open()

    async def _open(self) -> None:
        await self._set_state(CBState.OPEN)
        await self._redis.set(f"cb:{self._name}:opened_at", time.time())
        log.error("Circuit breaker OPENED", name=self._name)

    async def _set_state(self, state: CBState) -> None:
        await self._redis.set(f"cb:{self._name}:state", state.value)


# ──────────────────────────────────────────────────────────────────────────────
# Ingestion state — Redis-backed checkpoint per collector
# ──────────────────────────────────────────────────────────────────────────────

class IngestionState:
    """
    Thin key-value store for per-collector checkpoints.

    Key pattern: `ingestion:state:{platform}:{key}`
    """

    def __init__(self, redis: aioredis.Redis, platform: str) -> None:
        self._redis = redis
        self._prefix = f"ingestion:state:{platform}"

    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = await self._redis.get(f"{self._prefix}:{key}")
        return val.decode() if val else default

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if ttl:
            await self._redis.setex(f"{self._prefix}:{key}", ttl, value)
        else:
            await self._redis.set(f"{self._prefix}:{key}", value)

    async def delete(self, key: str) -> None:
        await self._redis.delete(f"{self._prefix}:{key}")

    async def all(self) -> Dict[str, str]:
        keys = await self._redis.keys(f"{self._prefix}:*")
        if not keys:
            return {}
        values = await self._redis.mget(*keys)
        prefix_len = len(self._prefix) + 1
        return {
            k.decode()[prefix_len:]: v.decode()
            for k, v in zip(keys, values) if v
        }


# ──────────────────────────────────────────────────────────────────────────────
# Collector stats — lightweight counters in Redis
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CollectorStats:
    platform: str
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    posts_collected_total: int = 0
    posts_ingested_total: int = 0
    errors_total: int = 0
    rate_limit_hits: int = 0
    circuit_state: str = CBState.CLOSED.value
    is_enabled: bool = True


class StatsTracker:
    def __init__(self, redis: aioredis.Redis, platform: str) -> None:
        self._redis = redis
        self._p = f"ingestion:stats:{platform}"

    async def incr(self, field: str, amount: int = 1) -> None:
        await self._redis.hincrby(self._p, field, amount)

    async def set_field(self, field: str, value: str) -> None:
        await self._redis.hset(self._p, field, value)

    async def get_all(self) -> Dict[str, str]:
        raw = await self._redis.hgetall(self._p)
        return {k.decode(): v.decode() for k, v in raw.items()}


# ──────────────────────────────────────────────────────────────────────────────
# Base collector
# ──────────────────────────────────────────────────────────────────────────────

class BaseCollector(ABC):
    """
    Abstract base for all platform collectors.

    Subclasses implement:
      - `collect()` — fetch raw posts from the platform API and return
                      a list of PostIngest objects ready for ingestion.

    `run_once()` handles:
      - circuit-breaker gate
      - rate-limit enforcement
      - tenacity retry on transient errors
      - stats tracking
      - calling ingest_batch()
    """

    platform: Platform

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=False
            )
        return self._redis

    async def _get_state(self) -> IngestionState:
        r = await self._get_redis()
        return IngestionState(r, self.platform.value)

    async def _get_stats(self) -> StatsTracker:
        r = await self._get_redis()
        return StatsTracker(r, self.platform.value)

    async def _get_circuit(self) -> CircuitBreaker:
        r = await self._get_redis()
        return CircuitBreaker(r, self.platform.value)

    @abstractmethod
    async def collect(self) -> List[PostIngest]:
        """
        Fetch posts from the platform.  Must be idempotent — duplicate
        posts are filtered downstream by the ingestion service.
        """

    async def run_once(self) -> Dict[str, Any]:
        """
        Execute one collection cycle.  Returns a stats dict.
        """
        from app.services.ingestion_service import ingest_batch

        stats = await self._get_stats()
        circuit = await self._get_circuit()
        now = datetime.now(timezone.utc).isoformat()

        await stats.set_field("last_run", now)

        try:
            await circuit.before_call()
        except CircuitBreakerOpen:
            log.warning("Collector skipped — circuit open", platform=self.platform.value)
            return {"status": "circuit_open", "platform": self.platform.value}

        collected: List[PostIngest] = []
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((ConnectionError, TimeoutError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=30),
            ):
                with attempt:
                    collected = await self.collect()

            await circuit.on_success()
            await stats.incr("posts_collected_total", len(collected))
            await stats.set_field("last_success", now)

        except RateLimitExceeded as exc:
            await stats.incr("rate_limit_hits")
            log.warning(
                "Rate limit hit during collection",
                platform=self.platform.value,
                retry_after=exc.retry_after,
            )
            return {"status": "rate_limited", "retry_after": exc.retry_after}

        except Exception as exc:
            await circuit.on_failure()
            await stats.incr("errors_total")
            await stats.set_field("last_error", str(exc))
            log.error("Collector failed", platform=self.platform.value, error=str(exc))
            raise

        if not collected:
            log.debug("No new posts", platform=self.platform.value)
            return {"status": "ok", "collected": 0, "ingested": 0, "skipped": 0}

        result = await ingest_batch(collected)
        await stats.incr("posts_ingested_total", result.get("ingested", 0))

        log.info(
            "Collection cycle complete",
            platform=self.platform.value,
            **result,
        )
        return {"status": "ok", "platform": self.platform.value, **result}
