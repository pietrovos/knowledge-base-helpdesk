"""Keeping the helpdesk usable when the model provider is down or slow.

- Deadline: every model call gets a hard wall-clock limit, independent of SDK timeouts.
- Circuit breaker (Redis-backed, so the API and every worker share one view): after
  `threshold` availability failures inside `window` seconds the circuit opens and calls fail
  immediately for `cooldown` seconds; then a single probe is allowed (half-open). A successful
  probe closes the circuit, a failed one re-opens it.
- Fault injection: an admin-controlled switch that makes the next calls fail, time out or run
  slowly, on any provider. Used for outage drills and the "provider down" demo.
If Redis itself is unavailable the breaker fails open (calls proceed) rather than taking
drafting down with it.
"""

import concurrent.futures
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import redis

from app.config import get_settings
from app.services.llm import DraftRequest, LLMError, LLMProvider, LLMResult, get_llm

log = logging.getLogger(__name__)

CircuitState = Literal["closed", "open", "half_open"]
ChaosMode = Literal["none", "error", "timeout", "slow"]
# Failures that say "the provider is unhealthy". Refusals and malformed output are about one
# request, not the provider, so they don't trip the breaker.
TRIPPING = {"timeout", "unavailable", "rate_limited", "config"}


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        decode_responses=True,
    )


@dataclass
class BreakerStatus:
    state: CircuitState
    failures: int
    open_until: float | None
    last_error: str | None


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        threshold: int = 3,
        window: int = 60,
        cooldown: int = 30,
        r: redis.Redis | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.name, self.threshold, self.window, self.cooldown = name, threshold, window, cooldown
        self._r = r
        self._clock = clock
        self._k = lambda suffix: f"cb:{name}:{suffix}"

    @property
    def r(self) -> redis.Redis:
        return self._r or get_redis()

    def status(self) -> BreakerStatus:
        try:
            open_until, failures, last_error = self.r.mget(
                self._k("open_until"), self._k("failures"), self._k("last_error")
            )
        except redis.RedisError:
            return BreakerStatus("closed", 0, None, None)
        until = float(open_until) if open_until else None
        if until is None:
            state: CircuitState = "closed"
        elif self._clock() < until:
            state = "open"
        else:
            state = "half_open"
        return BreakerStatus(state, int(failures or 0), until, last_error)

    def before_call(self) -> None:
        st = self.status()
        if st.state == "open":
            raise LLMError("circuit_open", _open_message(st.open_until - self._clock()))
        if st.state == "half_open":
            # Exactly one caller gets to probe the provider; everyone else keeps failing fast.
            try:
                got = self.r.set(self._k("probe"), "1", nx=True, ex=max(5, self.cooldown))
            except redis.RedisError:
                return
            if not got:
                raise LLMError("circuit_open", _open_message(0))

    def record_success(self) -> None:
        keys = [self._k(k) for k in ("failures", "open_until", "probe", "last_error")]
        with contextlib.suppress(redis.RedisError):
            self.r.delete(*keys)

    def record_failure(self, error: LLMError) -> None:
        if error.kind not in TRIPPING:
            return
        try:
            now = self._clock()
            pipe = self.r.pipeline()
            pipe.incr(self._k("failures"))
            pipe.expire(self._k("failures"), self.window)
            pipe.set(self._k("last_error"), f"{error.kind}: {error}"[:300], ex=3600)
            failures = pipe.execute()[0]
            was_probing = self.r.delete(self._k("probe"))
            if was_probing or failures >= self.threshold:
                self.r.set(self._k("open_until"), now + self.cooldown, ex=self.cooldown * 20)
                log.warning(
                    "circuit %s opened after %s failures (%s)", self.name, failures, error.kind
                )
        except redis.RedisError:
            log.warning("redis unavailable; circuit breaker not updated")

    def reset(self) -> None:
        self.record_success()


def _open_message(seconds_left: float) -> str:
    wait = f" Retrying automatically in about {int(seconds_left) + 1}s." if seconds_left > 0 else ""
    return "AI drafting is paused because the model provider is failing." + wait


def get_chaos_mode() -> ChaosMode:
    try:
        return get_redis().get("chaos:llm") or "none"  # type: ignore[return-value]
    except redis.RedisError:
        return "none"


def set_chaos_mode(mode: ChaosMode) -> None:
    if mode == "none":
        get_redis().delete("chaos:llm")
    else:
        get_redis().set("chaos:llm", mode, ex=3600)  # drills switch themselves off after an hour


def with_deadline(fn: Callable[[], LLMResult], seconds: float) -> LLMResult:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn)
    try:
        return future.result(timeout=seconds)
    except concurrent.futures.TimeoutError:
        raise LLMError(
            "timeout",
            f"No response from the model provider within {seconds:.0f}s",
            int(seconds * 1000),
        ) from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class ResilientLLM:
    """Wraps any provider with fault injection, a deadline and the shared circuit breaker."""

    def __init__(self, inner: LLMProvider, breaker: CircuitBreaker, deadline: float) -> None:
        self.inner, self.breaker, self.deadline = inner, breaker, deadline
        self.name, self.model = inner.name, inner.model

    def draft(self, request: DraftRequest) -> LLMResult:
        self.breaker.before_call()
        try:
            result = with_deadline(lambda: self._call(request), self.deadline)
        except LLMError as e:
            self.breaker.record_failure(e)
            raise
        self.breaker.record_success()
        return result

    def _call(self, request: DraftRequest) -> LLMResult:
        chaos = get_chaos_mode()
        if chaos == "error":
            raise LLMError("unavailable", "Model provider error (503) [simulated outage]", 3)
        if chaos == "timeout":
            time.sleep(self.deadline + 1)  # the deadline fires first
        if chaos == "slow":
            time.sleep(min(8.0, self.deadline / 2))
        return self.inner.draft(request)


def llm_breaker() -> CircuitBreaker:
    return CircuitBreaker("llm")


def get_resilient_llm() -> ResilientLLM:
    s = get_settings()
    return ResilientLLM(get_llm(), llm_breaker(), deadline=s.llm_timeout_seconds + 5)
