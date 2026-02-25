"""
Standalone FastAPI app for running in each geographic region.

Deploy independently in each region. The main PulseCheck server sends
POST /check requests to this worker, which performs the health check
locally and returns the result.

Usage:
    uvicorn pulsecheck.checker.region_worker:app --host 0.0.0.0 --port 8001
"""

import time

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="PulseCheck Region Worker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUEST_TIMEOUT = 10  # seconds


class CheckRequest(BaseModel):
    url: str
    service_id: str


class CheckResponse(BaseModel):
    status: str  # "healthy", "degraded", or "down"
    response_time_ms: int | None = None
    status_code: int | None = None
    error_message: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "role": "region_worker"}


@app.post("/check", response_model=CheckResponse)
async def perform_check(req: CheckRequest) -> CheckResponse:
    """Perform a health check against the given URL and return the result."""
    status = "down"
    status_code = None
    response_time_ms = None
    error_message = None

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            start = time.monotonic()
            resp = await client.get(req.url)
            elapsed = time.monotonic() - start

            response_time_ms = int(elapsed * 1000)
            status_code = resp.status_code

            if 200 <= status_code < 300:
                status = "healthy"
            elif 300 <= status_code < 500:
                status = "degraded"
            else:
                status = "down"

    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        error_message = str(exc)
        status = "down"
    except httpx.HTTPError as exc:
        error_message = str(exc)
        status = "down"

    return CheckResponse(
        status=status,
        response_time_ms=response_time_ms,
        status_code=status_code,
        error_message=error_message,
    )
