# Campus reliability lab

A compact Fault Tolerance and Dependable Computing midterm. Three university services, a small dashboard, a deliberately weak baseline, a resilient mode and reproducible failure experiments. No Kubernetes or frontend build is required.

## Run on Windows

From the repository in PowerShell (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python -m scripts.local --mode ft
```

Open **http://127.0.0.1:8100**. `Ctrl+C` stops only the launcher's child processes. No activation or execution-policy change is necessary. On macOS/Linux use `.venv/bin/python` instead.

Baseline, after stopping FT:

```powershell
.\.venv\Scripts\python -m scripts.local --mode baseline
```

To run both simultaneously, add `--base-port 8300` to one launcher. All data, environments, tokens and logs are inside this repository. Baseline and FT use separate storage under `.runtime/`. The launcher refuses to replace a server on an occupied port.

## What is running

| Process | Default port | Purpose |
|---|---:|---|
| Gateway | 8100 | Dashboard, API, round-robin routing, retry, breaker, transcript fallback |
| Student | 8101 | Student and tuition listing |
| Payment 1 | 8102 | Payment creation and ledger |
| Academic | 8103 | Academic transcript |
| Database | 8104 | SQLite owner, atomic balance and ledger, backup and audit |
| Payment 2 | 8105 | Independent payment replica, FT only |

The baseline uses one payment process, one attempt, a one-second safety timeout, no breaker/fallback/idempotency, and intentionally separate commits for the balance and ledger. Both modes retain input validation and basic health endpoints. FT uses three attempts at most, 50/100 ms backoff, a 300 ms downstream timeout, and a breaker per endpoint (two failures, one-second cooldown). Retried writes reuse the same idempotency key. Infrastructure redundancy is payment replication plus routing/failover; backup/restore supplies an additional recovery mechanism.

The site uses fictitious students and integer minor currency units (100 tiyn = 1 KZT). It records a tuition payment; it does not contact a real bank. Baseline is intentionally unsuitable for real payments.

## Test and measure

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m scripts.experiments --trials 3
```

To audit the submitted numbers without rerunning the workload:

```powershell
.\.venv\Scripts\python -m scripts.verify_results results/final
```

Rebuild the PDF and editable HTML report:

```powershell
.\.venv\Scripts\python -m pip install --no-cache-dir -r requirements-report.txt
.\.venv\Scripts\python -m scripts.build_report --dataset results/final
```

Russian companion report, preserving English technical terms:

```powershell
.\.venv\Scripts\python -m scripts.build_report_ru --dataset results/final
```

This creates `docs/REPORT_RU.pdf` and `docs/REPORT_RU.html` using the same measured data. The PDF embeds Arial for Cyrillic support; on Windows the builder reads the installed fonts. On another OS, pass `--font-dir` pointing to a directory containing `arial.ttf` and `arialbd.ttf`.

`requirements-lock.txt` records the full tested application environment. Report dependencies are separate from the running services.

The experiment runner starts isolated systems on ports **8200–8205**, kills/restarts only its own processes, and stops them on completion. Every run uses a fresh directory. It evaluates both modes and alternates their order across trials.

```powershell
# Short demonstration of three required scenarios, both modes
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario crash --scenario timeout --scenario interruption

# Other scenarios: database, node, load, duplicate, backup, response_loss
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario duplicate
```

`results/latest.txt` points to the latest successful experiment folder. Each case has raw request timings, injection/restoration events, before/after audits and metrics in JSON. `summary.csv` compares all cases. Actual service JSON logs are in that folder's `logs/`. Interactive service logs are under `.runtime/<mode>/logs/`.

Availability is reported separately as successful full responses / all requests and as a sequential-probe time estimate. Degraded transcripts are counted separately, even though HTTP status is 200. Induced outage estimates are **not production MTTF predictions**. A blank metric means unobserved/not applicable, never an invented zero. See the report for the measurement conventions and sampling limitations.

## Inject a reversible fault into the interactive demo

Run in another terminal while `scripts.local` is running:

```powershell
.\.venv\Scripts\python -m scripts.inject academic --delay-ms 1400
# Request a transcript in the browser, then restore it:
.\.venv\Scripts\python -m scripts.inject academic

.\.venv\Scripts\python -m scripts.inject database --interrupt
# Submit a payment; FT rolls back the partial attempt and safely retries.

.\.venv\Scripts\python -m scripts.inject database --response-loss 1
# Commit succeeds but its acknowledgement is lost; retry returns the existing payment.
```

Controls require a random local token saved by the launcher; they are disabled when `DEMO_TOKEN` is empty. Actual process crashes and grouped node simulations are available through `scripts.experiments`. Do not expose this teaching application to a public network: it has no user authentication.

## Docker Compose

With Docker Desktop's Linux engine running:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose stop payment1
# Refresh the payment ledger; payment2 handles traffic.
docker compose start payment1
docker compose logs --no-color
docker compose down
```

Baseline uses the same code with explicit overrides and only one payment replica:

```powershell
docker compose -f compose.yaml -f compose.baseline.yaml config --quiet
docker compose -f compose.yaml -f compose.baseline.yaml up --build -d
docker compose -f compose.yaml -f compose.baseline.yaml down
```

Both Docker variants publish port 8100; stop one before starting the other. Bind-mounted database files stay in `.runtime/docker-ft` or `.runtime/docker-baseline`. The local experimental dataset does **not** claim Docker execution. Compose startup health checks verify process liveness; runtime passive failure detection happens in the gateway. `restart: unless-stopped` recovers exited FT containers, but an explicit `docker compose stop` keeps them stopped for the failover demonstration.

## Files to review and submit

- `app/`, `scripts/`, `tests/`, Docker files and pinned dependencies: implementation.
- `docs/architecture.md`: diagram and deployment boundaries.
- `docs/REPORT.html`: technical report with all 14 required sections; open in a browser and print if needed.
- `docs/REPORT.pdf`: rendered and visually verified submission report for Tastan Magzhan, CSE-2505M.
- `docs/REPORT_RU.pdf`: Russian version with English technical terms; the same 14 sections, author details and numerical results. Editable text is available in `docs/REPORT_RU.html`.
- `docs/DEMO.md`, `docs/DEFENSE.md`: a short demo and Russian defense notes.
- `docs/REQUIREMENTS_CHECKLIST.md`: rubric audit and environment limitations.
- `results/final/`: measured dataset and service logs for the submitted report.

## Troubleshooting and cleanup

- Port occupied: stop your previous launcher or choose `--base-port 8500`. Do not kill unrelated processes.
- Docker daemon unavailable: start Docker Desktop yourself or use the fully runnable local mode.
- Wrong mode/data: each mode has its own directory; restart after changing mode.
- Breaker remains OPEN immediately after repair: wait at least one second, then send another request to permit the HALF_OPEN probe.
- Negative balance or duplicate data in baseline: that is the intended failure demonstration. FT uses separate storage.
- Stop with `Ctrl+C` or the appropriate `docker compose down`. To reset demo data, stop services first and remove only the relevant `.runtime/<mode>/data` directory inside this repository. Experimental evidence under `results/` should be retained.
