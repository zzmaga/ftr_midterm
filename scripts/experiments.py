"""Real HTTP experiments with actual child-process termination; no generated benchmark numbers."""
import argparse
import asyncio
import csv
import json
import platform
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from scripts.local import Cluster, ROOT
from scripts.metrics import summarize

SCENARIOS = ["crash", "database", "timeout", "node", "interruption", "load", "duplicate", "backup", "response_loss"]


async def run(mode, scenario, trial, output, base):
    case = f"{mode}_{scenario}_{trial}"
    with Cluster(mode, base, ROOT / ".runtime" / "experiments" / output.name / case,
                 output / "logs" / case) as cluster:
        async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
            rows, events = [], []
            origin = time.perf_counter()
            def now():
                return time.perf_counter()-origin

            def event(action, **fields):
                e = {"action": action, "time_s": now(), "wall_time": time.time(), **fields}
                events.append(e)
                return e

            async def admin(name, path, body=None):
                r = await client.request("GET" if path == "audit" else "POST", cluster.url(name)+"/admin/"+path,
                    json=body, headers={"X-Demo-Token": cluster.token})
                r.raise_for_status()
                return r.json()

            async def request(path="payments", body=None, probe=True):
                request_id = str(uuid.uuid4())
                started = now()
                try:
                    r = await client.request("POST" if body else "GET", cluster.url()+"/api/"+path, json=body,
                        headers={"X-Request-ID": request_id})
                    data = r.json()
                    degraded = isinstance(data, dict) and data.get("degraded", False)
                    status, attempts = r.status_code, int(r.headers.get("X-Attempts", 0))
                    worker = r.headers.get("X-Worker", "")
                except httpx.TransportError:
                    status, attempts, degraded, worker, data = 0, 0, False, "", None
                row = {"request_id": request_id, "start_s": started, "end_s": now(), "status": status,
                    "full_success": 200 <= status < 300 and not degraded, "degraded": degraded,
                    "attempts": attempts, "worker": worker, "probe": probe,
                    "latency_ms": (now()-started)*1000, "path": path}
                rows.append(row)
                return row, data

            async def probes(n=5, path="payments"):
                for _ in range(n):
                    await request(path)
                    await asyncio.sleep(0.08)

            def payment(key):
                return {"student_id": "S001", "amount": 100, "idempotency_key": key}

            path = "transcript/S001" if scenario == "timeout" else "payments"
            setup = await client.post(cluster.url()+"/api/payments", json=payment("setup-payment"))
            setup.raise_for_status()
            await probes(4, path)
            before = await admin("database", "audit")
            injected = event("fault_injected", scenario=scenario)
            extra = {}
            if scenario in ("crash", "node", "database"):
                victims = ["database"] if scenario == "database" else ["payment1"]
                if scenario == "node":
                    victims.append("academic")  # Simulated node A contains two independently running processes.
                for name in victims:
                    cluster.kill(name)
                event("processes_killed", victims=victims)
                await probes(7)
                if scenario == "node":
                    # Check failure containment across the other business services.
                    extra["student_status"] = (await request("students", probe=False))[0]["status"]
                    extra["transcript_degraded"] = (await request("transcript/S001", probe=False))[0]["degraded"]
                for name in victims:
                    cluster.start_one(name)
                await asyncio.to_thread(cluster.wait_ready, victims)
                event("component_restored")
                await asyncio.sleep(1.05)
                await probes(5)
            elif scenario == "timeout":
                await admin("academic", "fault", {"delay_ms": 1400})
                await probes(5, path)
                extra["student_status"] = (await request("students", probe=False))[0]["status"]
                extra["payment_status"] = (await request("payments", probe=False))[0]["status"]
                await admin("academic", "fault", {})
                event("component_restored")
                await asyncio.sleep(1.1)
                await probes(5, path)
            elif scenario == "interruption":
                await admin("database", "fault", {"interrupt": True})
                row, _ = await request(body=payment("interrupted"))
                extra["after_first_attempt"] = await admin("database", "audit")
                await request(body=payment("interrupted"))
                event("component_restored")
                await probes(4)
            elif scenario == "response_loss":
                await admin("database", "fault", {"response_loss": 1})
                await request(body=payment("lost-ack"))
                await request(body=payment("lost-ack"))
                event("component_restored")
                await probes(4)
            elif scenario == "duplicate":
                # Concurrent deliveries exercise database uniqueness across both replicas.
                await asyncio.gather(*(request(body=payment("same-key"), probe=False) for _ in range(12)))
                event("component_restored")
                await probes(4)
            elif scenario == "load":
                semaphore = asyncio.Semaphore(30)
                async def one(i):
                    async with semaphore:
                        return await request(body=payment(f"load-{i}"), probe=False)
                load_start = now()
                await asyncio.gather(*(one(i) for i in range(120)))
                extra["load_duration_s"] = now()-load_start
                extra["load_throughput_rps"] = 120/extra["load_duration_s"]
                event("component_restored")
                await probes(4)
            elif scenario == "backup":
                await request(body=payment("before-checkpoint"))
                checkpoint = await admin("database", "audit")
                if mode == "ft":
                    await admin("database", "backup")
                # Restore a checkpoint after a valid later write to demonstrate recovery-point loss.
                await request(body=payment("after-checkpoint"))
                if mode == "ft":
                    await admin("database", "restore")
                    extra["checkpoint_restored"] = (await admin("database", "audit")) == checkpoint
                else:
                    extra["checkpoint_restored"] = False
                extra["checkpoint_payment_count"] = checkpoint["payment_count"]
                event("component_restored")
                await probes(4)
            after = await admin("database", "audit")
            ended = now()
            metrics = summarize(rows, ended)
            detections = []
            for file in cluster.logs.glob("*.jsonl"):
                for line in file.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if entry.get("action") in ("downstream_failure", "database_unavailable", "rollback", "partial_commit", "response_lost") and entry.get("wall_time", 0) >= injected["wall_time"]:
                        detections.append(entry["wall_time"]-injected["wall_time"])
            post = [r for r in rows if r["probe"] and r["start_s"] >= injected["time_s"] and r["full_success"]]
            restored = next((e for e in events if e["action"] == "component_restored"), None)
            summary = {"mode": mode, "scenario": scenario, "trial": trial, **metrics,
                "detection_ms": min(detections)*1000 if detections else None,
                "service_recovery_ms": (post[0]["end_s"]-injected["time_s"])*1000 if post else None,
                "component_restore_ms": (restored["time_s"]-injected["time_s"])*1000 if restored else None,
                "consistent": after["consistent"], "duplicate_keys": after["duplicate_keys"],
                "payment_count": after["payment_count"],
                "workers": ",".join(sorted({r["worker"] for r in rows if r["worker"]}))}
            artifact = {"summary": summary, "events": events, "requests": rows,
                        "state_before": before, "state_after": after, "extra": extra}
            (output / f"{case}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
            print(f"{case}: {metrics['successful_requests']}/{metrics['requests']} full responses; consistent={after['consistent']}", flush=True)
            return summary


async def main_async(args):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "results" / (args.output or stamp)
    output = output.resolve()
    if not output.is_relative_to(ROOT / "results") or output.exists():
        raise ValueError("Output must be a NEW directory inside results/")
    output.mkdir(parents=True)
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
                "python": platform.python_version(), "backend": "local subprocesses", "trials": args.trials,
                "note": "Injected faults, not a prediction of production MTTF. Node failure is a process-group simulation."}
    (output / "environment.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    rows = []
    for trial in range(1, args.trials+1):
        # Alternate order to reduce systematic warm-up/order effects.
        for mode in (["baseline", "ft"] if trial % 2 else ["ft", "baseline"]):
            for scenario in args.scenario or SCENARIOS:
                rows.append(await run(mode, scenario, trial, output, args.base_port))
                with (output / "summary.csv").open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
    (ROOT / "results" / "latest.txt").write_text(output.name, encoding="utf-8")
    print(f"Results: {output}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--scenario", choices=SCENARIOS, action="append")
    p.add_argument("--base-port", type=int, default=8200)
    p.add_argument("--output")
    args = p.parse_args()
    if args.trials < 1:
        p.error("trials must be positive")
    asyncio.run(main_async(args))
