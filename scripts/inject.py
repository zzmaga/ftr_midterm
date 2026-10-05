"""Configure reversible HTTP faults on an already running local demo."""
import argparse
from pathlib import Path

import httpx

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("service", choices=["student", "payment1", "payment2", "academic", "database"])
    p.add_argument("--mode", choices=["baseline", "ft"], default="ft")
    p.add_argument("--base-port", type=int, default=8100)
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--failures", type=int, default=0)
    p.add_argument("--interrupt", action="store_true")
    p.add_argument("--response-loss", type=int, default=0)
    args = p.parse_args()
    offsets = {"student": 1, "payment1": 2, "academic": 3, "database": 4, "payment2": 5}
    token = (Path(__file__).resolve().parents[1] / ".runtime" / args.mode / "demo-token.txt").read_text().strip()
    with httpx.Client(trust_env=False) as c:
        r = c.post(f"http://127.0.0.1:{args.base_port+offsets[args.service]}/admin/fault",
            headers={"X-Demo-Token": token}, json={"delay_ms": args.delay_ms, "failures": args.failures,
                "interrupt": args.interrupt, "response_loss": args.response_loss})
        r.raise_for_status()
        print(r.json())
