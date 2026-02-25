import time
from datetime import datetime, timezone
from importlib.metadata import metadata, PackageNotFoundError

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from pulsecheck.api.v1.routes.services import router as services_router

app = FastAPI(title="PulseCheck")
app.include_router(services_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_start_time = time.monotonic()
_request_count = 0


@app.middleware("http")
async def count_requests(request: Request, call_next):
    global _request_count
    _request_count += 1
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/status")
def status() -> dict:
    uptime_seconds = time.monotonic() - _start_time
    return {
        "uptime_seconds": round(uptime_seconds, 2),
        "request_count": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/version")
def version() -> dict:
    try:
        meta = metadata("pulsecheck")
        ver = meta["Version"]
    except PackageNotFoundError:
        # Fallback: read version directly from pyproject.toml
        from pathlib import Path
        import tomllib

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            ver = tomllib.loads(pyproject.read_text())["project"]["version"]
        else:
            ver = "unknown"
    return {"version": ver}
