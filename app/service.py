"""Run as three independent HTTP services selected by SERVICE."""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from app.common import INSTANCE, log, make_app
from app.database_models import PaymentInput

SERVICE = os.getenv("SERVICE", "student")
DB_URL = os.getenv("DB_URL", "http://127.0.0.1:8104")
app = make_app(f"University {SERVICE} service")


@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient(timeout=0.8, trust_env=False)
    yield
    await app.state.client.aclose()


app.router.lifespan_context = lifespan


async def forward(request, path, method="GET", body=None):
    try:
        r = await app.state.client.request(method, DB_URL+path, json=body,
            headers={"X-Request-ID": request.state.request_id})
        return JSONResponse(r.json(), r.status_code, headers={"X-Worker": INSTANCE})
    except httpx.TransportError as exc:
        log("database_unavailable", failure_type=type(exc).__name__, request_id=request.state.request_id)
        return JSONResponse({"detail": "Database temporarily unavailable"}, 503)


if SERVICE == "student":
    @app.get("/students")
    async def students(request: Request):
        return await forward(request, "/students")
elif SERVICE == "academic":
    @app.get("/transcript/{student_id}")
    async def transcript(student_id: str, request: Request):
        return await forward(request, f"/transcript/{student_id}")
elif SERVICE == "payment":
    @app.get("/payments")
    async def payments(request: Request):
        return await forward(request, "/payments")

    @app.post("/payments")
    async def pay(p: PaymentInput, request: Request):
        return await forward(request, "/payments", "POST", p.model_dump())
else:
    raise ValueError("Unknown SERVICE")
