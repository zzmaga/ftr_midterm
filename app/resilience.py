"""Small per-endpoint circuit breaker and bounded exponential retry policy."""
import asyncio
import time
from dataclasses import dataclass

import httpx

from app.common import log


@dataclass
class Breaker:
    threshold: int = 2
    cooldown: float = 1.0
    failures: int = 0
    opened_at: float = 0
    state: str = "CLOSED"

    def allow(self):
        if self.state == "OPEN" and time.monotonic()-self.opened_at >= self.cooldown:
            self.state = "HALF_OPEN"
            log("breaker_half_open")
            return True
        return self.state == "CLOSED"

    def success(self):
        if self.state != "CLOSED":
            log("breaker_closed")
        self.state, self.failures = "CLOSED", 0

    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold or self.state == "HALF_OPEN":
            self.state, self.opened_at = "OPEN", time.monotonic()
            log("breaker_open")


class DownstreamUnavailable(Exception):
    def __init__(self, attempts):
        self.attempts = attempts


class ResilientClient:
    def __init__(self, ft=True, timeout=0.3):
        self.ft = ft
        self.client = httpx.AsyncClient(timeout=timeout if ft else 1.0, trust_env=False)
        self.breakers = {}
        self.cursor = {}

    async def close(self):
        await self.client.aclose()

    async def request(self, endpoints, path, method="GET", body=None, headers=None):
        budget = 3 if self.ft else 1
        key = tuple(endpoints)
        offset = self.cursor.get(key, 0) if self.ft else 0
        self.cursor[key] = offset + 1
        attempts = 0
        for attempt in range(budget):
            chosen = None
            for shift in range(len(endpoints)):
                endpoint = endpoints[(offset+attempt+shift) % len(endpoints)]
                breaker = self.breakers.setdefault(endpoint, Breaker())
                if not self.ft or breaker.allow():
                    chosen = endpoint
                    break
            if chosen is None:
                log("circuit_rejected", request_id=(headers or {}).get("X-Request-ID"))
                break
            attempts += 1
            try:
                response = await self.client.request(method, chosen+path, json=body, headers=headers)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError("downstream server error", request=response.request, response=response)
                breaker.success()
                return response, attempts
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if self.ft:
                    breaker.failure()
                log("downstream_failure", endpoint=chosen, attempt=attempts,
                    request_id=(headers or {}).get("X-Request-ID"), failure_type=type(exc).__name__)
                if attempt+1 < budget:
                    delay = 0.05 * 2**attempt
                    log("retry_backoff", attempt=attempts, delay_ms=delay*1000)
                    await asyncio.sleep(delay)
        raise DownstreamUnavailable(attempts)
