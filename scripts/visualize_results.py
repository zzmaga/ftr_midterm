"""Export a self-contained dashboard that opens directly in any browser, without a server."""
import argparse
import json
from pathlib import Path

from app.experiment_results import ROOT, RESULTS, load_results


def build(directory):
    data = load_results(directory)
    template = (ROOT / "app" / "static" / "results.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    output = Path(directory) / "dashboard.html"
    output.write_text(template.replace("/*EXPERIMENT_DATA*/null", payload), encoding="utf-8")
    return output.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()
    directory = args.directory or RESULTS / (RESULTS / "latest.txt").read_text(encoding="utf-8").strip()
    print(f"Open in your browser: {build(directory)}")
