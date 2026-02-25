import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import metadata, PackageNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.checker.engine import HealthCheckEngine
from pulsecheck.db.session import get_session
from pulsecheck.models.health_check import HealthCheck
from pulsecheck.models.service import Service

_engine = HealthCheckEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _engine.start()
    yield
    await _engine.stop()


app = FastAPI(title="PulseCheck", lifespan=lifespan)

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


@app.get("/api/v1/services/{service_id}/checks")
async def get_service_checks(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    # Verify the service exists
    svc = await session.get(Service, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")

    stmt = (
        select(HealthCheck)
        .where(HealthCheck.service_id == service_id)
        .order_by(HealthCheck.checked_at.desc())
        .limit(100)
    )
    result = await session.execute(stmt)
    checks = result.scalars().all()

    return [
        {
            "id": str(check.id),
            "service_id": str(check.service_id),
            "status": check.status.value,
            "response_time_ms": check.response_time_ms,
            "status_code": check.status_code,
            "error_message": check.error_message,
            "checked_at": check.checked_at.isoformat(),
        }
        for check in checks
    ]
