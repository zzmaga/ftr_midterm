# Assignment checklist

Source: MIDTERM FTR.docx supplied by the user. The earlier ChatGPT conversation is planning context, not experimental evidence.

- [x] Repository inspected: initial README only; no existing application or AGENTS.md.
- [x] At least three independent university services: students, payments, academic records.
- [x] Runnable baseline and fault-tolerant modes with the same business API.
- [x] Infrastructure mechanisms: payment replicas, gateway load balancing/failover, SQLite backup/restore.
- [x] Software mechanisms: bounded retries/backoff, timeout, circuit breaker, idempotency, savepoint/rollback, health checks, transcript degradation.
- [x] Execute all six required scenarios in both modes: crash, database outage, timeout, simulated node loss, interrupted transaction, concurrent load. Nine scenarios x two modes x three trials = 54 cases in `results/final/`.
- [x] Collect detection/recovery times, request counts, system state and data consistency. JSON traces, summary CSV and real service logs are included.
- [x] Calculate MTTF, MTBF, MTTR, availability, observed failure rate and recovered request counts. Report section 10 explains finite-window estimates, unavailable values and sampling limits.
- [x] Architecture diagram and fault analysis including single points of failure and RAID/ECC concepts. Report sections 4-6 and `architecture.md`.
- [x] Report with all fourteen prescribed sections and real references: `REPORT.pdf` and editable `REPORT.html`, 10 PDF pages visually checked. Personal fields are blank as requested.
- [x] Reproducible experiments, logs, comparison tables and meaningful tests: 17 passing tests; 54 cases independently recomputed and verified.
- [x] Demonstration guide covering at least three failures; Russian defense preparation: `DEMO.md` and `DEFENSE.md`.
- [x] Final requirement and evidence audit. Commit/push status is recorded in Git rather than self-referential documentation.

## Verification boundaries

- [x] Both Compose configurations validated with Docker Compose v2.39.4. Baseline resolves to exactly five services (no payment2).
- [ ] Docker container execution: not executed in the current environment; Docker engine unavailable. Run the Docker commands in README when the engine is available.
- [ ] Browser visual interaction: not executed; the browser-control inventory was empty. HTML delivery and business API behavior were verified through HTTP integration tests.
- [ ] DOCX export: not provided. The available document runtime has no bundled LibreOffice for the required render-and-review gate. The assignment's technical-report deliverable is provided as visually verified PDF and editable HTML.
- [ ] Physical multi-host failure: intentionally simulated as grouped process termination; not claimed as measured hardware protection.

No natural/production failure rate is inferred from injected faults. The gateway, database owner, host and disk remain single points of failure. Interrupted debug runs (`results/evaluation`, `results/measured`) and the early smoke run are excluded from Git and are not report evidence.
