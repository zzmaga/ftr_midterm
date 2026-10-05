"""Request availability and probe-derived outage estimates are deliberately kept separate."""
import statistics
import math


def summarize(rows, observation_end):
    ordered = sorted(rows, key=lambda r: r["end_s"])
    start = min(r["start_s"] for r in ordered)
    span = observation_end-start
    # Only sequential availability probes define time intervals. Load requests do not.
    probes = [r for r in ordered if r["probe"]]
    outages, opened = [], None
    for row in probes:
        if not row["full_success"] and opened is None:
            opened = row["end_s"]
        elif row["full_success"] and opened is not None:
            outages.append((opened, row["end_s"], True))
            opened = None
    if opened is not None:
        outages.append((opened, observation_end, False))
    downtime = sum(b-a for a, b, _ in outages)
    uptime = span-downtime
    complete = [b-a for a, b, done in outages if done]
    failures = len(outages)
    mttf = uptime/failures if failures else None
    mttr = statistics.mean(complete) if complete else None
    success = sum(r["full_success"] for r in rows)
    recovered = sum(r["full_success"] and r["attempts"] > 1 for r in rows)
    retried = sum(r["attempts"] > 1 for r in rows)
    return {"requests": len(rows), "successful_requests": success,
            "failed_requests": len(rows)-success, "degraded_responses": sum(r["degraded"] for r in rows),
            "recovered_requests": recovered, "retried_requests": retried,
            "retry_recovery_rate": recovered/retried if retried else None,
            "request_availability": success/len(rows),
            "observation_s": span, "uptime_s": uptime, "downtime_s": downtime,
            "outage_episodes": failures, "completed_recoveries": len(complete),
            "mttf_s": mttf, "mttr_s": mttr,
            "mtbf_s": mttf+mttr if mttf is not None and mttr is not None else None,
            "time_availability": uptime/span if probes else None,
            "failure_rate_per_s": failures/uptime if uptime else None,
            "p95_latency_ms": sorted(r["latency_ms"] for r in rows)[max(0, math.ceil(len(rows)*0.95)-1)]}
