"""Shared demo configuration, structured logs and explicitly enabled fault controls."""
import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

MODE = os.getenv("MODE", "ft")
INSTANCE = os.getenv("INSTANCE", "service")
TOKEN = os.getenv("DEMO_TOKEN", "")


def log(action, **fields):
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                      "wall_time": time.time(), "service": INSTANCE,
                      "mode": MODE, "action": action, **fields}), flush=True)


def authorize(request: Request):
    if not TOKEN or request.headers.get("X-Demo-Token") != TOKEN:
        raise HTTPException(403, "Demo controls are disabled or token is invalid")


class Fault(BaseModel):
    delay_ms: int = Field(0, ge=0, le=5000)
    failures: int = Field(0, ge=0, le=10000)
    interrupt: bool = False
    response_loss: int = Field(0, ge=0, le=100)


def make_app(name):
    app = FastAPI(title=name)
    app.state.fault = Fault()

    @app.post("/admin/fault")
    def fault(spec: Fault, request: Request):
        authorize(request)
        app.state.fault = spec
        log("fault_configured", **spec.model_dump())
        return spec

    @app.get("/health")
    def health():
        return {"status": "healthy", "instance": INSTANCE, "mode": MODE}

    @app.middleware("http")
    async def trace(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        if not request.url.path.startswith(("/admin", "/health")):
            f = app.state.fault
            if f.delay_ms:
                await asyncio.sleep(f.delay_ms / 1000)
            if f.failures:
                f.failures -= 1
                from fastapi.responses import JSONResponse
                log("injected_failure", request_id=request_id, failure_type="transient_503")
                return JSONResponse({"detail": "Injected transient failure"}, 503)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Instance"] = INSTANCE
        log("request", request_id=request_id, path=request.url.path,
            status=response.status_code, latency_ms=round((time.perf_counter()-started)*1000, 3))
        return response

    return app
