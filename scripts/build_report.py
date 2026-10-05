"""Build a PDF and editable HTML from the submitted experiment dataset."""
import argparse
import csv
import html
import json
import statistics
from pathlib import Path

from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]


def fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def mean(rows, key):
    values = [r[key] for r in rows if r[key] is not None]
    return statistics.mean(values) if values else None


def architecture():
    d = Drawing(475, 280)
    def box(x, y, w, h, lines):
        d.add(Rect(x, y, w, h, fillColor=colors.HexColor("#f2f5f8"), strokeColor=colors.HexColor("#aebccb"), radius=5))
        for i, text in enumerate(lines):
            d.add(String(x+w/2, y+h-16-i*12, text, textAnchor="middle", fontName="Helvetica", fontSize=9))
    def arrow(x1,y1,x2,y2):
        d.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor("#566c81")))
        d.add(Polygon([x2,y2,x2-3,y2+6,x2+3,y2+6],fillColor=colors.HexColor("#566c81"),strokeColor=None))
    box(170,239,135,35,["Browser / experiments"])
    box(130,176,215,46,["Gateway", "Retry / timeout / breaker / failover"])
    arrow(238,239,238,222)
    xs=[0,122,244,366]
    for x, title in zip(xs,["Student","Payment 1","Payment 2","Academic"]):
        box(x,107,109,39,[title, "separate process"])
        arrow(238,176,x+54,146)
        arrow(x+54,107,238,81)
    box(151,35,174,46,["Storage API / SQLite", "Balance + ledger transaction"])
    box(351,35,124,46,["Checkpoint backup", "manual restoration"])
    d.add(Line(325,58,351,58,strokeColor=colors.HexColor("#566c81")))
    d.add(String(0,10,"All services emit JSON events. The harness records requests, faults and audits.",fontSize=9))
    return d


def build(dataset, output):
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(dataset.glob("*.json")) if p.name != "environment.json"]
    rows = [c["summary"] for c in cases]
    assert len(rows) == 54, "The submitted report requires a complete three-trial dataset"
    env = json.loads((dataset / "environment.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=8, textColor=colors.HexColor("#172535")))
    styles.add(ParagraphStyle(name="SmallBody", parent=styles["Body"], fontSize=8.5, leading=11))
    styles.add(ParagraphStyle(name="TableText", parent=styles["Body"], fontSize=8, leading=10, spaceAfter=0))
    styles.add(ParagraphStyle(name="TableHead", parent=styles["TableText"], textColor=colors.white, fontName="Helvetica-Bold"))
    styles["Title"].fontName="Helvetica-Bold"
    styles["Title"].fontSize=27
    styles["Title"].leading=33
    styles["Title"].textColor=colors.black
    styles["Heading1"].fontSize=17
    styles["Heading1"].leading=21
    styles["Heading1"].spaceAfter=12
    styles["Heading1"].textColor=colors.black
    styles["Heading2"].fontSize=12
    styles["Heading2"].textColor=colors.black
    story, web = [], []
    def p(text, small=False):
        story.append(Paragraph(html.escape(text), styles["SmallBody" if small else "Body"]))
        web.append(f"<p>{html.escape(text)}</p>")
    def heading(text, level=1):
        story.append(Paragraph(html.escape(text), styles[f"Heading{level}"]))
        web.append(f"<h{level+1}>{html.escape(text)}</h{level+1}>")
    def page():
        story.append(PageBreak())
        web.append('<div class="pagebreak"></div>')
    def table(headers, data, widths):
        cells = [[Paragraph(html.escape(str(c)), styles["TableHead"] if i==0 else styles["TableText"]) for c in row] for i,row in enumerate([headers]+data)]
        t = Table(cells,colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#203c58')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f0f4f8')]),
            ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#d9d9d9')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.extend([t,Spacer(1,12)])
        web.append('<table><thead><tr>'+''.join(f'<th>{html.escape(str(c))}</th>' for c in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{html.escape(str(c))}</td>' for c in r)+'</tr>' for r in data)+'</tbody></table>')
    def group(mode,scenario=None):
        return [r for r in rows if r["mode"] == mode and (scenario is None or r["scenario"] == scenario)]

    story.extend([Spacer(1,42),Paragraph("Fault Tolerant University Information System",styles["Title"]),Spacer(1,15)])
    web.append('<h1>Fault Tolerant University Information System</h1>')
    p("Midterm technical report | Fault Tolerance and Dependable Computing")
    p("Campus reliability lab | 5 October 2026")
    story.append(Spacer(1,35))
    for label in ["Student name", "Student ID", "Group", "Instructor"]:
        p(label+": __________________________________________")
    story.append(Spacer(1,30))
    p("A compact, executable university platform compares an intentionally weak baseline with a fault-tolerant configuration. Three business services and one shared SQLite owner expose failures, recovery and transaction consistency through real HTTP experiments.")
    p("The submitted dataset contains 54 controlled runs: nine scenarios, two configurations and three trials. Measurements use local processes on one Windows computer. Physical node failure is modelled by stopping a group of processes; it is not a multi-host hardware test.")
    p("Repository: https://github.com/zzmaga/ftr_midterm")
    p("Evidence: results/final | Reproduction: README.md | Demonstration: docs/DEMO.md")
    page()
    heading("1 Introduction and project motivation")
    p("A university platform should not duplicate tuition payments when a reply is lost, nor make payment access depend on an optional transcript service. This project demonstrates both availability and integrity. A small architecture makes each protection visible in code and supports a short oral demonstration.")
    p("The main result is fault containment: a second payment process preserves payment access after one replica fails, while transactions and idempotency prevent partial or repeated payment effects. A shared database outage still interrupts all database-dependent operations. Redundancy is therefore useful only within its actual failure boundary.")
    heading("2 System requirements and assumptions")
    p("The assignment requires a baseline, at least three independent services, at least five realistic faults, two infrastructure mechanisms, four software mechanisms, controlled before/after experiments, reliability calculations and a demonstration of three recovery scenarios. All six explicitly listed scenarios are implemented, with three additional integrity/recovery exercises.")
    p("Teaching acceptance criteria are: no failed payment-list requests during a single payment-replica crash in FT; zero balance/ledger discrepancies and duplicate keys in all FT cases; restored full responses after repair; and recorded detection, restoration and request evidence. These are experiment-specific criteria, not a production SLA.")
    p("Two fictitious students start with 100000 tiyn tuition due each. Amounts use integer tiyn (100 tiyn per KZT). Every experiment first commits an unmeasured 100-tiyn seed payment, so persistence is checked on non-empty data. Fault controls are local and token protected. Authentication, real bank integration and multi-host deployment are outside the scope.")
    heading("3 Dependability and fault model")
    p("Dependability here includes availability, integrity and recoverability. Reliability concerns uninterrupted service over an interval; availability permits repair and counts the usable fraction. A fault is a cause, an error is an incorrect internal outcome, and a failure is a violation of the service contract.")
    p("Example: termination of payment1 is a fault; connection refusal at the gateway is an error; an unsuccessful client payment request is a service failure. In FT the gateway can route to payment2, so the error is masked. Lost acknowledgement is an omission fault: a payment may already exist even though the client observed failure.")
    p("Faults are crash-stop, transient delay/error, omission after commit and an injected workflow interruption. Grouped process loss models a permanent node fault until explicit repair. Byzantine peers, arbitrary disk corruption, simultaneous host loss and malicious requests are excluded. A degraded transcript is useful but does not satisfy the full-response availability definition.")
    page()
    heading("4 Reliability and failure analysis")
    p("The qualitative failure analysis below traces each injected fault to its client impact and remaining risk. Severity is descriptive; no unsupported occurrence probabilities or risk-priority scores are assigned.")
    table(["Fault", "Error and service effect", "Protection and residual risk"], [
        ["Application crash", "Payment endpoint cannot connect to payment1.", "Replica and failover preserve access; gateway and database remain single points."],
        ["Database outage", "Storage connection fails; business APIs cannot read/write.", "Bounded retry and controlled 503; explicit restart restores access. No database replica."],
        ["Service timeout", "Academic reply exceeds the downstream timeout.", "Breaker limits calls; labelled cached response. Full transcript is unavailable."],
        ["Node A simulation", "Payment1 and academic are killed together.", "Payment2 survives; student works. Whole-host failure remains unprotected."],
        ["Interrupted payment", "Balance changes before ledger insertion.", "FT transaction rolls back; baseline exposes a discrepancy."],
        ["Concurrent load", "Queueing and shared storage contention increase latency.", "Two workers distribute traffic; shared SQLite serializes writes."],
        ["Duplicate or lost reply", "A payment request is delivered more than once.", "Shared unique key and payload check return the original payment."],
        ["Checkpoint restore", "Operator restores an earlier database state.", "Consistent backup recovers that state but loses post-checkpoint writes."]
    ],[94,181,200])
    p("A simple fault tree for payment unavailability is: gateway failure OR storage failure OR (payment1 unavailable AND payment2 unavailable) OR a common host/network failure. For baseline, one payment failure alone is sufficient. Integrity failure has separate causes: missing atomicity, missing idempotency or recovery to an older checkpoint without reconciliation.")
    p("Under an illustrative independence assumption, two replicas each with availability A=0.99 have combined availability 1-(1-A)^2=0.9999. If the gateway and storage each also have 0.99 availability, the series product is 0.99 x 0.99 x 0.9999 = 0.98000199. These are hypothetical values, not measured estimates; a shared host also violates independence.")
    page()
    heading("5 System architecture")
    story.extend([architecture(),Spacer(1,15)])
    web.append('<pre>Browser / experiments\n        |\nGateway: round robin, retry, timeout, breaker\n        |\nStudent | Payment 1 | Payment 2 | Academic\n        |\nStorage API / SQLite ---- Checkpoint backup\n        |\nJSON events + HTTP traces + consistency audits</pre>')
    p("Figure 1. Each business service runs as an independent HTTP process. FT adds payment2. The gateway is a small FastAPI application rather than an external reverse proxy, making routing decisions and circuit state easy to inspect. Mermaid source is supplied in docs/architecture.md.")
    p("Ports are 8100 for the gateway, 8101 for students, 8102 and 8105 for payments, 8103 for academic records, and 8104 for storage. Experiments use 8200-8205; tests use 8400-8405. The launcher checks that ports are free and owns only its child process trees.")
    p("All business services access the same storage API. Only its process opens SQLite. This single transaction authority makes payment keys consistent across replicas. The gateway holds a per-endpoint breaker and an in-memory transcript cache; cache loss after gateway restart is acceptable and explicitly produces a degraded response without cached data.")
    p("The simulated node A contains payment1 and academic; node B contains payment2 and student. Both are logical groups on one computer. JSON logging is integrated into each process, while the experiment harness collects request timing and state snapshots separately.")
    page()
    heading("6 Hardware fault tolerance design")
    p("Infrastructure protection consists of redundant payment instances, round-robin routing with failover, and backup restoration. A killed payment process is bypassed by the gateway. The local experiment harness later restarts it; this restart is scheduled by the experiment, not an autonomous production orchestrator.")
    p("SQLite backup creates a consistent checkpoint file [2]. The restore experiment deliberately removes a valid later payment by returning to the checkpoint, making recovery-point loss explicit. This is logical storage recovery on one disk, not independent storage redundancy. A production design would copy backups to another fault domain and reconcile later transactions.")
    p("RAID can use disk redundancy to tolerate selected disk faults; it does not undo a logically incorrect write or replace backups. ECC memory can detect and correct supported memory bit errors; it does not repair an application algorithm. Both concepts are documented only. Neither RAID nor ECC is claimed as implemented or measured.")
    heading("7 Software fault tolerance design")
    table(["Mechanism", "Implementation and boundary"],[
        ["Retry and timeout", "Gateway permits at most 3 attempts, with 50/100 ms backoff and a 300 ms HTTPX timeout. Baseline uses 1 attempt and a 1 s safety timeout [3]."],
        ["Circuit breaker", "Two downstream failures open a per-endpoint circuit. After 1 s, one HALF_OPEN probe can close it or reopen it [5]."],
        ["Idempotency", "A unique SQLite key is checked inside BEGIN IMMEDIATE. Same key and payload return the existing row; conflicting payload receives 409."],
        ["Checkpoint and rollback", "A savepoint precedes balance change; interruption rolls back. The outer transaction commits balance and ledger together [1]."],
        ["Health and degradation", "Liveness routes expose process status. Academic failure returns explicitly marked cached data; payments never fall back to invented success."]
    ],[112,363])
    heading("8 Implementation")
    p("Python, FastAPI, HTTPX and SQLite keep the application small. app/service.py is launched independently for three service roles. app/database.py owns storage and auditing; app/resilience.py owns recovery policy. The baseline deliberately omits idempotency and commits the balance before inserting its payment row. Both variants retain validation.")
    p("Meaningful automated tests cover concurrent cross-replica duplicates, conflicting payloads, lost replies after commit, exact rollback state, backup restore, breaker transitions, non-retried 4xx responses and reliability calculations. Seventeen tests passed. Compose configurations validate successfully; container runtime execution was unavailable because the Docker engine was not running [4].")
    page()
    heading("9 Experimental methodology")
    p(f"Execution environment: {env['platform']}; Python {env['python']}. Dataset start (UTC): {env['started_utc']}. The workload ran against real local HTTP processes. Three trials per scenario and mode produce 54 isolated runs; baseline/FT execution order alternates by trial.")
    p("Each run has a new database directory. A seed payment is committed, four warm-up probes are recorded, and then the fault is injected. Crash/database/node cases make seven affected-period probes, restart owned processes, wait for liveness and a 1.05 s breaker cooldown, then make five recovery probes. Probes sleep 80 ms between completed requests; timeout cases have five affected and five recovery probes and a 1.1 s post-repair wait.")
    p("The timeout fault adds 1400 ms of server delay. The node fault kills payment1 and academic together. The load case issues 120 unique 100-tiyn payments with concurrency 30; duplicate uses twelve simultaneous deliveries of one key. Interruption fires once between balance change and ledger insertion. Lost response returns a simulated 503 after commit. Backup restores an earlier consistent checkpoint and verifies the exact audit state.")
    table(["Measurement", "Operational definition"],[
        ["Detection time", "Injection event to first observed downstream failure, storage error or rollback log. Wall clocks share one host. No observed signal is n/a."],
        ["Service recovery", "Injection to first subsequent full successful probe. If failover masks the fault, this is time to first confirming success, not outage duration."],
        ["Component restoration", "Injection to the harness's completed restart/reset marker. This is distinct from successful service recovery."],
        ["Request availability", "Full successful responses / measured requests. Degraded academic HTTP 200 responses are excluded and counted separately."],
        ["Consistency", "initial_due - due equals SUM(payment.amount), no duplicate keys, and the seed payment remains. Baseline HTTP success alone can hide corruption."],
        ["Recovered requests", "Full successful client requests that required more than one gateway attempt. No claim is made about unobserved downstream retries."]
    ],[112,363])
    p("Timing uses perf_counter for request/event intervals; structured logs use a UTC wall clock to correlate failure detection. Request time availability is sampled, not continuously observed. Concurrent load requests do not define outage intervals; pre/post probes can miss an outage within the burst. The report therefore interprets time metrics only for crash, database, timeout and node cases.")
    page()
    heading("10 Results and comparison")
    summary_data=[]
    names={"crash":"Application crash","database":"Database outage","timeout":"Academic timeout","node":"Node A loss","interruption":"Interrupted payment","load":"Concurrent load","duplicate":"Duplicate delivery","backup":"Checkpoint restore","response_loss":"Lost acknowledgement"}
    for scenario,name in names.items():
        b,f=group("baseline",scenario),group("ft",scenario)
        def counts(g):
            return f"{sum(r['successful_requests'] for r in g)}/{sum(r['requests'] for r in g)}"
        summary_data.append([name,counts(b),counts(f),f"{sum(r['consistent'] for r in b)}/3",f"{sum(r['consistent'] for r in f)}/3"])
    table(["Scenario", "Baseline full", "FT full", "B consistent", "FT consistent"],summary_data,[145,88,82,80,80])
    p("Table 1. Counts combine three trials. Consistent columns count trials meeting both business invariants. Extra student/payment checks in the node and timeout scenarios are included in the response totals. Backup is a deliberate recovery exercise; baseline has no checkpoint restoration facility.")
    b,f=group("baseline"),group("ft")
    total=sum(r["requests"] for r in b)
    p(f"Across the mixed workload, baseline had {sum(r['failed_requests'] for r in b)} failed full responses out of {total}; FT had {sum(r['failed_requests'] for r in f)} out of {sum(r['requests'] for r in f)}. FT recovered {sum(r['recovered_requests'] for r in f)} requests within retries. These totals summarize this scenario mix and should not be interpreted as a general availability SLO.")
    p("Replica failover eliminated payment-list failures during application crash. FT node loss still degraded the academic endpoint, which is deliberately counted as loss of full service. Both modes lost full database-dependent responses during storage outage; neither has storage replication. Baseline duplicate and lost-reply cases returned successful HTTP responses while violating transaction identity, showing why request availability and integrity must be evaluated separately.")
    load_data=[]
    for mode in ["baseline","ft"]:
        subset=group(mode,"load")
        cps=[c for c in cases if c["summary"]["mode"]==mode and c["summary"]["scenario"]=="load"]
        rates=[c["extra"]["load_throughput_rps"] for c in cps]
        load_data.append([mode,fmt(statistics.mean(rates),1),f"{min(rates):.1f} - {max(rates):.1f}",fmt(mean(subset,"p95_latency_ms"),1)])
    table(["Mode", "Mean requests/s", "Trial range", "Mean case p95 ms"],load_data,[90,125,140,120])
    p("Table 2. Throughput counts the 120 completed burst requests; all burst requests succeeded in the submitted dataset. The p95 column is the mean of each case's nearest-rank latency percentile, including its pre/post probes. Three trials do not establish a statistically robust performance advantage.")
    page()
    heading("Reliability calculations for Section 10",2)
    p("Let T be the observation span from first request start to final audit; D be the union of probe-observed outage intervals; U=T-D; F be the number of outage episodes; and C be completed recovery episodes. An outage begins at completion of the first failed full probe and ends at completion of the first subsequent full success. An open final outage is censored at T.")
    p("MTTF estimate = U/F; MTTR = sum(completed outage durations)/C; MTBF estimate = MTTF + MTTR; time availability = U/T; observed failure rate = F/U. Request availability = full successes/N; retry recovery fraction = successful retried requests/all retried requests. Missing denominators produce n/a. The repairable-cycle MTTF/MTBF values include finite-window exposure, so they are descriptive induced-failure estimates, not natural lifetime measurements.")
    metric_data=[]
    for scenario in ["crash","database","timeout","node"]:
        for mode in ["baseline","ft"]:
            g=group(mode,scenario)
            U=sum(r["uptime_s"] for r in g); T=sum(r["observation_s"] for r in g)
            F=sum(r["outage_episodes"] for r in g); C=sum(r["completed_recoveries"] for r in g)
            mttr=sum(r["mttr_s"]*r["completed_recoveries"] for r in g if r["mttr_s"] is not None)/C if C else None
            mttf=U/F if F else None
            metric_data.append([scenario,mode,fmt(mttf),fmt(mttr),fmt(mttf+mttr if mttf is not None and mttr is not None else None),f"{U/T*100:.1f}%",fmt(F/U)])
    table(["Scenario","Mode","MTTF s","MTTR s","MTBF s","Time A","Rate /s"],metric_data,[76,61,68,68,68,66,68])
    p("Table 3. Pooled exposure and recovery durations over three trials. FT node time availability uses payment probes; its separate degraded transcript request is counted in Table 1, not as a payment outage. FT crash and node therefore have no observed payment outage from which to estimate MTTF or MTTR.")
    detection=[]
    for scenario in ["crash","database","timeout","node","interruption","response_loss"]:
        b,f=group("baseline",scenario),group("ft",scenario)
        detection.append([scenario,fmt(mean(b,"detection_ms"),1),fmt(mean(f,"detection_ms"),1),fmt(mean(b,"service_recovery_ms"),1),fmt(mean(f,"service_recovery_ms"),1)])
    table(["Scenario","B detect ms","FT detect ms","B confirm ms","FT confirm ms"],detection,[99,92,92,96,96])
    p("Table 4. Mean injection-to-detection and injection-to-first-success intervals. They include workload scheduling. Longer baseline timeout probes can also delay the script's scheduled repair, so recovery differences are partly a harness/workload effect and must not be attributed entirely to faster infrastructure repair.",small=True)
    page()
    heading("11 Discussion and limitations")
    p("The experiment-specific availability and integrity goals were met for the selected FT cases: every single-replica crash retained full payment responses, all FT audits were consistent, and normal probes resumed after repairs. The dataset does not justify a broader claim of continuous service under database or whole-host loss. A real deployment would need a redundant gateway, database replication, separate hosts and a tested backup recovery policy.")
    p("The load test is bounded and the database serializes payments under a process lock. Replication therefore mainly addresses process failure, not write scaling. The baseline intentionally has weak transaction boundaries; its difference from FT is a pedagogical contrast rather than a comparison with a competently designed production payment system.")
    p("Timeout and retry settings were selected for a local demonstration. HTTPX timeouts constrain network phases, not a strict end-to-end deadline [3]. The service-to-database timeout remains 800 ms. Retries occur only at the gateway to avoid multiplicative retry storms. Production work should add jitter, load shedding, an overall deadline, bounded caches and request tracing across hosts.")
    p("Circuit state and transcript cache live in one gateway process. Health endpoints prove liveness, not database readiness. Failure detection is passive when traffic encounters a broken endpoint. The node simulation does not reproduce CPU, kernel, disk or network-switch failures. Physical hardware redundancy and RAID/ECC were not measured.")
    p("Only three repetitions, one host, finite workloads and intentionally injected failures are available. No confidence interval or natural failure-rate claim is supported. Probe estimates miss the interval before the first failure is observed and may miss short outages between probes. No unmeasured outage during a load burst is silently treated as proven availability.")
    p("Restore discards post-checkpoint payments and keys. It must be performed during a maintenance/quiescence window and followed by reconciliation. The demonstration's backup sits on the same disk. The application is a local teaching tool with unauthenticated business endpoints and must not be publicly exposed.")
    heading("12 Conclusion")
    p("A small university system is sufficient to demonstrate observable fault tolerance. Application replication protects a selected service from process loss; a breaker contains repeated dependency failures; transaction rollback and idempotency preserve payment integrity. The experiments also show the limits: a shared database and host still define a common failure boundary. Raw requests, event logs and audit snapshots make these claims reproducible.")
    page()
    heading("13 References")
    refs=[
        ("1", "SQLite. Atomic Commit in SQLite.", "https://www.sqlite.org/atomiccommit.html"),
        ("2", "SQLite. Online Backup API.", "https://www.sqlite.org/backup.html"),
        ("3", "HTTPX. Timeouts.", "https://www.python-httpx.org/advanced/timeouts/"),
        ("4", "Docker. Control startup and shutdown order in Compose.", "https://docs.docker.com/compose/how-tos/startup-order/"),
        ("5", "Microsoft Learn. Circuit Breaker pattern.", "https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker"),
        ("6", "FastAPI. Deployment concepts.", "https://fastapi.tiangolo.com/deployment/concepts/")]
    for number,title,url in refs:
        p(f"[{number}] {title} Accessed 5 October 2026.",small=True)
        story.append(Paragraph(f'<link href="{url}" color="#244bc3">{html.escape(url)}</link>',styles["SmallBody"]))
        web.append(f'<p><a href="{url}">{url}</a></p>')
    p("The primary documentation supports the mechanisms and deployment choices [1-6]. All measured values come from this repository's experimental records, not from the reference examples.")
    heading("14 Appendix source code configuration logs and additional results")
    table(["Artifact", "Contents"],[
        ["app/", "Gateway, shared fault controls, business services, resilience policy, database and dashboard."],
        ["scripts/", "Owned-process launcher; reproducible experiments; metrics; evidence verification; report builder."],
        ["tests/", "17 automated unit and HTTP integration tests."],
        ["compose.yaml and baseline override", "Container topology, liveness checks, replicas, separate bind-mounted datasets."],
        ["results/final/", "54 JSON cases, summary.csv, environment metadata and per-service JSON event logs."],
        ["docs/", "Architecture diagram, assignment checklist, demo and defense notes, generated report."]
    ],[166,309])
    p("Reproduce: python -m pytest -q; python -m scripts.experiments --trials 3; python -m scripts.verify_results results/final. Experiments write new folders, leaving the submitted dataset unchanged. Rebuild this report with python -m scripts.build_report --dataset results/final after installing requirements-report.txt.",small=True)
    p("Source logs record request IDs, UTC timestamps, service instance, mode, action, status and latency. Transaction events carry their payment key. Fault, attempt and recovery fields appear on applicable events. Missing fields do not imply fabricated measurements.",small=True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#68788a"))
        canvas.drawString(60,30,"Campus reliability lab | Midterm technical report")
        canvas.drawRightString(A4[0]-60,30,str(doc.page))
        canvas.restoreState()
    doc=SimpleDocTemplate(str(output / "REPORT.pdf"),pagesize=A4,rightMargin=60,leftMargin=60,topMargin=48,bottomMargin=50,
        title="Fault Tolerant University Information System",author="",subject="Measured midterm reliability report")
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    css="body{font:16px/1.6 system-ui,sans-serif;color:#172535;max-width:980px;margin:50px auto;padding:0 25px}h1,h2,h3{color:#000;line-height:1.2}h2{margin-top:35px}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{border:1px solid #d9d9d9;padding:10px;text-align:left}th{background:#203c58;color:white}tr:nth-child(even){background:#f0f4f8}pre{white-space:pre-wrap;background:#f2f5f8;padding:20px}@media print{body{margin:0;font-size:10pt}.pagebreak{break-before:page}tr{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit}}"
    (output / "REPORT.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>University system midterm report</title><style>'+css+'</style><main>'+''.join(web)+'</main></html>',encoding="utf-8")
    print(f"Created {output / 'REPORT.pdf'} and REPORT.html from {len(rows)} measured cases")


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",type=Path,default=ROOT / "results" / "final")
    p.add_argument("--output",type=Path,default=ROOT / "docs")
    args=p.parse_args()
    build(args.dataset,args.output)
