"""Health check endpoints."""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from eldenops.config.settings import settings
from eldenops.db.engine import engine

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "eldenops-api"}


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check - verifies all dependencies are available."""
    checks = {}
    all_ok = True

    # Check database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        all_ok = False

    # Check Redis connection
    try:
        redis_client = redis.from_url(str(settings.redis_url))
        await redis_client.ping()
        await redis_client.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        all_ok = False

    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
