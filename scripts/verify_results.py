"""Recompute saved metrics and verify scientific/transaction evidence without rerunning workloads."""
import argparse
import csv
import json
import math
from pathlib import Path

from scripts.metrics import summarize


def verify(root):
    with (root / "summary.csv").open(encoding="utf-8") as stream:
        summaries = list(csv.DictReader(stream))
    assert len(summaries) == 54, f"Expected 9 scenarios x 2 modes x 3 trials, found {len(summaries)}"
    for s in summaries:
        name = f"{s['mode']}_{s['scenario']}_{s['trial']}"
        case = json.loads((root / f"{name}.json").read_text())
        saved = case["summary"]
        start = min(r["start_s"] for r in case["requests"])
        recalculated = summarize(case["requests"], start+saved["observation_s"])
        for key, value in recalculated.items():
            if isinstance(value, (float, int)):
                assert math.isclose(value, saved[key], abs_tol=1e-8), (name, key)
            else:
                assert value == saved[key], (name, key)
        assert case["state_before"]["payment_count"] == 1, name
        assert case["state_after"]["payment_count"] >= 1, name
        if s["mode"] == "ft":
            assert saved["consistent"], name
            if s["scenario"] in ("interruption", "response_loss", "duplicate"):
                assert saved["payment_count"] == 2 and saved["duplicate_keys"] == 0, name
            if s["scenario"] == "crash":
                assert saved["failed_requests"] == 0 and "payment2" in saved["workers"], name
            if s["scenario"] == "backup":
                assert case["extra"]["checkpoint_restored"], name
            if s["scenario"] == "timeout":
                assert saved["degraded_responses"] > 0, name
                logs = (root / "logs" / name / "gateway.jsonl").read_text()
                for state in ("breaker_open", "breaker_half_open", "breaker_closed"):
                    assert state in logs, (name, state)
        elif s["scenario"] in ("interruption", "response_loss", "duplicate"):
            assert not saved["consistent"], name
    print(f"Verified {len(summaries)} cases: recomputed metrics, preserved seed payment, rollback, idempotency, failover, breaker and backup evidence.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path, nargs="?", default=Path("results/final"))
    verify(p.parse_args().directory)
