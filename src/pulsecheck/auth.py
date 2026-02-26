import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.models.api_key import ApiKey

# Paths that never require authentication
PUBLIC_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/ws/",
    "/api/v1/status",
    "/api/v1/version",
    "/api/v1/status-page",
)


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new random API key with a 'pc_' prefix."""
    return "pc_" + secrets.token_urlsafe(32)


async def verify_api_key(session: AsyncSession, key: str) -> ApiKey | None:
    """Verify an API key and return the ApiKey record if valid."""
    key_hash = hash_api_key(key)
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()
    if api_key:
        api_key.last_used_at = datetime.now(timezone.utc)
        await session.commit()
    return api_key


def _is_public_path(path: str) -> bool:
    """Check if a request path is public (no auth required)."""
    for prefix in PUBLIC_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return True
    # Non-API paths are public (e.g. frontend static files)
    if not path.startswith("/api/"):
        return True
    return False


async def api_key_middleware(request: Request, call_next):
    """Middleware that enforces API key authentication on protected endpoints."""
    path = request.url.path

    # Allow public paths through without auth
    if _is_public_path(path):
        return await call_next(request)

    # Use the same session factory as dependency injection (respects test overrides)
    from pulsecheck.db.session import get_session

    session_factory = request.app.dependency_overrides.get(get_session, get_session)
    session_gen = session_factory()
    session = await anext(session_gen)
    try:
        # Check if any API keys exist; if not, allow access (bootstrap mode)
        count_stmt = select(ApiKey.id).limit(1)
        result = await session.execute(count_stmt)
        if result.scalar_one_or_none() is None:
            return await call_next(request)

        # Require X-API-Key header
        api_key_header = request.headers.get("X-API-Key")
        if not api_key_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key header"},
            )

        # Verify the key
        api_key = await verify_api_key(session, api_key_header)
        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or inactive API key"},
            )
    finally:
        try:
            await anext(session_gen)
        except StopAsyncIteration:
            pass

    return await call_next(request)
