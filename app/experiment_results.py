"""Read measured CSV summaries for the dashboard; never substitute sample data."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load_results(directory):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(RESULTS.resolve()):
        raise ValueError("Results must be inside the project's results directory")
    with (directory / "summary.csv").open(encoding="utf-8", newline="") as stream:
        rows = []
        for source in csv.DictReader(stream):
            row = {key: source[key] for key in ("mode", "scenario")}
            if row["mode"] not in ("baseline", "ft"):
                raise ValueError("Unknown experiment mode")
            for key in ("trial", "requests", "successful_requests", "failed_requests", "degraded_responses", "recovered_requests"):
                row[key] = int(source[key])
                if row[key] < 0:
                    raise ValueError("Negative experiment count")
            row["errors"] = row["failed_requests"] - row["degraded_responses"]
            if row["errors"] < 0 or row["requests"] != row["successful_requests"] + row["failed_requests"]:
                raise ValueError("Inconsistent response counts")
            if source["consistent"].lower() not in ("true", "false"):
                raise ValueError("Invalid consistency result")
            row["consistent"] = source["consistent"].lower() == "true"
            rows.append(row)
    if not rows:
        raise ValueError("No completed cases in summary.csv")
    environment = directory / "environment.json"
    return {"run": directory.name, "cases": rows,
            "environment": json.loads(environment.read_text(encoding="utf-8")) if environment.exists() else {}}


def latest_results():
    marker = RESULTS / "latest.txt"
    name = marker.read_text(encoding="utf-8").strip() if marker.exists() else "final"
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("Invalid latest results directory")
    return load_results(RESULTS / name)
