"""Regenerate derived summary metrics from immutable recorded requests (never invent timings)."""
import argparse
import csv
import json
from pathlib import Path

from scripts.metrics import summarize


def recalculate(directory):
    summaries=[]
    for path in sorted(directory.glob("*.json")):
        if path.name == "environment.json":
            continue
        case=json.loads(path.read_text(encoding="utf-8"))
        rows=case["requests"]
        end=min(r["start_s"] for r in rows)+case["summary"]["observation_s"]
        case["summary"].update(summarize(rows,end))
        path.write_text(json.dumps(case,indent=2),encoding="utf-8")
        summaries.append(case["summary"])
    with (directory / "summary.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"Recomputed {len(summaries)} summaries from recorded request traces")


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("directory",type=Path)
    recalculate(p.parse_args().directory)
