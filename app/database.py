"""SQLite owner. Ledger and tuition balance are one atomic business transaction in FT mode."""
import os
import sqlite3
import threading
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.common import MODE, authorize, log, make_app

app = make_app("University storage")
DATA = Path(os.getenv("DATA_DIR", ".runtime/data"))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "university.sqlite"
BACKUP = DATA / "checkpoint.sqlite"
lock = threading.RLock()


def connect():
    conn = sqlite3.connect(DB, timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


with connect() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT, initial_due INTEGER, due INTEGER);
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, idem_key TEXT, student_id TEXT,
      amount INTEGER, FOREIGN KEY(student_id) REFERENCES students(id));
    CREATE TABLE IF NOT EXISTS grades(student_id TEXT, course TEXT, grade TEXT);
    INSERT OR IGNORE INTO students VALUES('S001','Aida Sapar',100000,100000);
    INSERT OR IGNORE INTO students VALUES('S002','Daniyar Omar',100000,100000);
    """)
    if MODE == "ft":
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS payment_key ON payments(idem_key)")
    if not c.execute("SELECT 1 FROM grades LIMIT 1").fetchone():
        c.executemany("INSERT INTO grades VALUES(?,?,?)", [("S001", "Fault Tolerance", "A"), ("S001", "Distributed Systems", "B+")])


class Payment(BaseModel):
    student_id: str = Field(min_length=1, max_length=30)
    amount: int = Field(gt=0, le=100000, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=100)


@app.get("/students")
def students():
    with lock, connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM students")]


@app.get("/transcript/{student_id}")
def transcript(student_id: str):
    with lock, connect() as c:
        if not c.execute("SELECT 1 FROM students WHERE id=?", (student_id,)).fetchone():
            raise HTTPException(404, "Student not found")
        return {"student_id": student_id, "grades": [dict(r) for r in c.execute("SELECT course,grade FROM grades WHERE student_id=?", (student_id,))], "degraded": False}


@app.get("/payments")
def payments():
    with lock, connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM payments ORDER BY id DESC")]


@app.post("/payments")
def pay(p: Payment, request: Request):
    with lock:
        c = connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            if MODE == "ft":
                existing = c.execute("SELECT * FROM payments WHERE idem_key=?", (p.idempotency_key,)).fetchone()
                if existing:
                    if existing["student_id"] != p.student_id or existing["amount"] != p.amount:
                        raise HTTPException(409, "Key already belongs to a different payment")
                    return {**dict(existing), "duplicate": True}
            student = c.execute("SELECT * FROM students WHERE id=?", (p.student_id,)).fetchone()
            if not student:
                raise HTTPException(404, "Student not found")
            if p.amount > student["due"]:
                raise HTTPException(409, "Payment exceeds outstanding tuition")
            log("transaction_begin", transaction_id=p.idempotency_key, request_id=request.state.request_id, due_before=student["due"])
            if MODE == "ft":
                c.execute("SAVEPOINT payment_checkpoint")
                log("checkpoint", transaction_id=p.idempotency_key)
            c.execute("UPDATE students SET due=due-? WHERE id=?", (p.amount, p.student_id))
            if MODE == "baseline":
                c.commit()  # Deliberately unsafe multi-step baseline workflow.
            if app.state.fault.interrupt:
                app.state.fault.interrupt = False
                if MODE == "ft":
                    c.execute("ROLLBACK TO payment_checkpoint")
                    c.rollback()
                    log("rollback", transaction_id=p.idempotency_key, due_restored=student["due"])
                else:
                    log("partial_commit", transaction_id=p.idempotency_key)
                raise HTTPException(503, "Injected interruption between balance update and ledger insert")
            cur = c.execute("INSERT INTO payments(idem_key,student_id,amount) VALUES(?,?,?)", (p.idempotency_key, p.student_id, p.amount))
            payment_id = cur.lastrowid
            c.commit()
            log("transaction_commit", transaction_id=p.idempotency_key, payment_id=payment_id)
            if app.state.fault.response_loss:
                app.state.fault.response_loss -= 1
                log("response_lost", transaction_id=p.idempotency_key)
                return JSONResponse({"detail": "Injected lost acknowledgement after commit"}, 503)
            return {"id": payment_id, "idem_key": p.idempotency_key, "student_id": p.student_id, "amount": p.amount, "duplicate": False}
        finally:
            c.close()  # Rolls back any uncommitted transaction, including validation errors.


@app.get("/admin/audit")
def audit(request: Request):
    authorize(request)
    with lock, connect() as c:
        rows = [dict(r) for r in c.execute("""SELECT s.id,s.initial_due,s.due,COALESCE(SUM(p.amount),0) AS paid,
            s.initial_due-s.due-COALESCE(SUM(p.amount),0) AS discrepancy
            FROM students s LEFT JOIN payments p ON p.student_id=s.id GROUP BY s.id""")]
        duplicates = c.execute("SELECT COUNT(*) FROM (SELECT idem_key FROM payments GROUP BY idem_key HAVING COUNT(*)>1)").fetchone()[0]
        return {"consistent": all(r["discrepancy"] == 0 for r in rows) and duplicates == 0,
                "balances": rows, "duplicate_keys": duplicates,
                "payment_count": c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]}


@app.post("/admin/backup")
def backup(request: Request):
    authorize(request)
    with lock, connect() as source, sqlite3.connect(BACKUP) as target:
        source.backup(target)
    log("backup_created")
    return {"checkpoint": BACKUP.name}


@app.post("/admin/restore")
def restore(request: Request):
    authorize(request)
    if not BACKUP.exists():
        raise HTTPException(404, "No checkpoint")
    with lock, sqlite3.connect(BACKUP) as source, connect() as target:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise HTTPException(409, "Invalid checkpoint")
        source.backup(target)
    log("backup_restored")
    return {"restored": True, "warning": "Writes after the checkpoint are discarded"}
