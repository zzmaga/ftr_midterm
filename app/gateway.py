import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse

from app.common import MODE, make_app
from app.database_models import PaymentInput
from app.resilience import DownstreamUnavailable, ResilientClient

app = make_app("Campus reliability lab")
ROUTES = {
    "student": [os.getenv("STUDENT_URL", "http://127.0.0.1:8101")],
    "payment": os.getenv("PAYMENT_URLS", "http://127.0.0.1:8102,http://127.0.0.1:8105").split(","),
    "academic": [os.getenv("ACADEMIC_URL", "http://127.0.0.1:8103")],
}


@asynccontextmanager
async def lifespan(app):
    app.state.downstream = ResilientClient(MODE == "ft")
    app.state.cache = {}
    yield
    await app.state.downstream.close()


app.router.lifespan_context = lifespan


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/status")
async def status():
    result = {}
    for service, urls in ROUTES.items():
        result[service] = []
        for url in urls:
            try:
                r = await app.state.downstream.client.get(url+"/health")
                healthy = r.status_code == 200
            except Exception:
                healthy = False
            breaker = app.state.downstream.breakers.get(url)
            result[service].append({"url": url, "healthy": healthy, "breaker": breaker.state if breaker else "CLOSED"})
    return {"mode": MODE, "services": result}


async def proxy(service, path, request, method="GET", body=None):
    try:
        r, attempts = await app.state.downstream.request(ROUTES[service], path, method, body,
            {"X-Request-ID": request.state.request_id})
        data = r.json()
        if service == "academic" and r.status_code == 200:
            app.state.cache[path] = data
        return JSONResponse(data, r.status_code, headers={"X-Attempts": str(attempts), "X-Worker": r.headers.get("X-Worker", "")})
    except DownstreamUnavailable as exc:
        if MODE == "ft" and service == "academic":
            data = app.state.cache.get(path)
            return JSONResponse({"degraded": True, "stale": data is not None, "cached_transcript": data,
                "detail": "Transcript service unavailable; student and payment services remain independent"},
                200, headers={"X-Attempts": str(exc.attempts)})
        return JSONResponse({"detail": "Service temporarily unavailable; retry with the same payment key"},
            503, headers={"X-Attempts": str(exc.attempts)})


@app.get("/api/students")
async def students(request: Request):
    return await proxy("student", "/students", request)


@app.get("/api/payments")
async def payments(request: Request):
    return await proxy("payment", "/payments", request)


@app.post("/api/payments")
async def pay(p: PaymentInput, request: Request):
    return await proxy("payment", "/payments", request, "POST", p.model_dump())


@app.get("/api/transcript/{student_id}")
async def transcript(student_id: str, request: Request):
    return await proxy("academic", f"/transcript/{student_id}", request)
