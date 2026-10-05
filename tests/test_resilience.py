import asyncio
import time

import httpx
import pytest

from app.resilience import Breaker, DownstreamUnavailable, ResilientClient
from scripts.metrics import summarize


def test_breaker_allows_only_one_half_open_probe():
    b = Breaker(cooldown=0.01)
    b.failure()
    assert b.allow()
    b.failure()
    assert b.state == "OPEN" and not b.allow()
    b.opened_at = time.monotonic()-1
    assert b.allow() and b.state == "HALF_OPEN"
    assert not b.allow()
    b.success()
    assert b.state == "CLOSED" and b.allow()


def test_failed_half_open_probe_reopens():
    b = Breaker(state="HALF_OPEN")
    b.failure()
    assert b.state == "OPEN"


def test_retries_preserve_payment_and_request_id():
    async def run():
        seen = []
        def transport(r):
            seen.append((r.content, r.headers["X-Request-ID"]))
            return httpx.Response(503 if len(seen) == 1 else 200, json={"id": 1})
        c = ResilientClient()
        await c.client.aclose()
        c.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            r, attempts = await c.request(["http://test"], "/payments", "POST", {"idempotency_key": "abc"}, {"X-Request-ID": "req"})
            assert r.status_code == 200 and attempts == 2
            assert seen[0] == seen[1]
        finally:
            await c.close()
    asyncio.run(run())


@pytest.mark.parametrize("status", [404, 409, 422])
def test_client_errors_are_never_retried(status):
    async def run():
        c = ResilientClient()
        await c.client.aclose()
        c.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={})))
        try:
            r, attempts = await c.request(["http://test"], "/payments")
            assert r.status_code == status and attempts == 1
        finally:
            await c.close()
    asyncio.run(run())


def test_baseline_does_not_retry():
    async def run():
        c = ResilientClient(False)
        await c.client.aclose()
        c.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        try:
            with pytest.raises(DownstreamUnavailable) as exc:
                await c.request(["http://test"], "/")
            assert exc.value.attempts == 1
        finally:
            await c.close()
    asyncio.run(run())


def test_metrics_outages_are_not_failed_request_counts():
    rows = [{"start_s": t-0.1, "end_s": t, "full_success": success, "attempts": 1,
             "degraded": False, "probe": True, "latency_ms": 100}
            for t, success in [(1, True), (2, False), (3, False), (5, True)]]
    m = summarize(rows, 6)
    assert m["failed_requests"] == 2 and m["outage_episodes"] == 1
    assert m["mttr_s"] == 3
    assert m["downtime_s"] == 3
    assert m["mtbf_s"] == pytest.approx(m["mttf_s"]+3)


def test_no_failure_does_not_mean_infinite_measured_mttf():
    rows = [{"start_s": 0, "end_s": 1, "full_success": True, "attempts": 1,
             "degraded": False, "probe": True, "latency_ms": 1000}]
    m = summarize(rows, 2)
    assert m["mttf_s"] is None and m["mttr_s"] is None and m["time_availability"] == 1
