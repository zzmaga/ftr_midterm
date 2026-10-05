"""Owns only child processes started by this launcher. All mutable files stay in the repo."""
import argparse
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


class Cluster:
    def __init__(self, mode="ft", base=8100, directory=None, logs=None):
        self.mode, self.base = mode, base
        self.directory = Path(directory or ROOT / ".runtime" / mode).resolve()
        if not self.directory.is_relative_to(ROOT):
            raise ValueError("Data directory must be inside this repository")
        self.logs = Path(logs or self.directory / "logs").resolve()
        if not self.logs.is_relative_to(ROOT):
            raise ValueError("Log directory must be inside this repository")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(24)
        self.processes, self.files = {}, []
        self.names = ["database", "student", "payment1", "academic", "gateway"]
        if mode == "ft":
            self.names.insert(3, "payment2")
        self.offsets = {"gateway": 0, "student": 1, "payment1": 2, "academic": 3, "database": 4, "payment2": 5}

    def url(self, name="gateway"):
        return f"http://127.0.0.1:{self.base+self.offsets[name]}"

    def start_one(self, name):
        port = self.base+self.offsets[name]
        with socket.socket() as probe:
            # Windows keeps closed connections in TIME_WAIT: a bind probe falsely
            # reports those as occupied. Check for a listening server instead.
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} already has a server; choose another base port")
        module = "database" if name == "database" else "gateway" if name == "gateway" else "service"
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1", "MODE": self.mode,
               "INSTANCE": name, "SERVICE": "payment" if name.startswith("payment") else name,
               "DATA_DIR": str(self.directory / "data"), "DEMO_TOKEN": self.token,
               "DB_URL": self.url("database"), "STUDENT_URL": self.url("student"),
               "ACADEMIC_URL": self.url("academic"), "PAYMENT_URLS": self.url("payment1") +
               ((","+self.url("payment2")) if self.mode == "ft" else "")}
        stream = (self.logs / f"{name}.jsonl").open("a", encoding="utf-8")
        self.files.append(stream)
        self.processes[name] = subprocess.Popen([sys.executable, "-m", "uvicorn", f"app.{module}:app",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=stream, stderr=stream,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def wait_ready(self, names=None):
        with httpx.Client(timeout=0.3, trust_env=False) as client:
            for name in names or self.names:
                deadline = time.monotonic()+20
                while time.monotonic() < deadline:
                    if self.processes[name].poll() is not None:
                        raise RuntimeError(f"{name} exited; see {self.logs / (name+'.jsonl')}")
                    try:
                        if client.get(self.url(name)+"/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError(f"{name} did not become ready")

    def start(self):
        try:
            for name in self.names:
                self.start_one(name)
            self.wait_ready()
        except BaseException:
            self.stop()
            raise
        return self

    def kill(self, name):
        p = self.processes.get(name)
        if p and p.poll() is None:
            if os.name == "nt":
                # A Windows venv executable is a launcher with a child interpreter.
                # Terminate only this owned process tree, never by executable name.
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                p.kill()
            p.wait(timeout=5)

    def restart(self, name):
        self.kill(name)
        self.start_one(name)
        self.wait_ready([name])

    def stop(self):
        for name in reversed(self.names):
            self.kill(name)
        for stream in self.files:
            stream.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["baseline", "ft"], default="ft")
    p.add_argument("--base-port", type=int, default=8100)
    args = p.parse_args()
    with Cluster(args.mode, args.base_port) as cluster:
        # Token is local-only and intentionally not committed to evidence.
        (cluster.directory / "demo-token.txt").write_text(cluster.token, encoding="utf-8")
        print(f"Open {cluster.url()} | mode={args.mode}", flush=True)
        print(f"Token file: {cluster.directory / 'demo-token.txt'}\nCtrl+C stops all owned services.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
