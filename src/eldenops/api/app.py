"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from eldenops.api.routes import auth, health, tenants, analytics, reports, webhooks, attendance, github, projects, ws, goals
from eldenops.config.settings import settings
from eldenops.db.engine import close_db, init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting EldenOps API...")

    # Initialize database
    if not settings.is_production:
        # Only auto-create tables in development
        # In production, use Alembic migrations
        await init_db()
        logger.info("Database tables initialized")

    yield

    # Cleanup
    await close_db()
    logger.info("EldenOps API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="EldenOps API",
        description="Team analytics platform API - combining Discord and GitHub data with AI insights",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Next.js dev server
            "http://localhost:3005",  # Next.js dev server (alt port)
            "http://localhost:8000",  # API server
        ]
        if not settings.is_production
        else ["https://your-domain.com"],  # Update in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
    app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
    app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["Attendance"])
    app.include_router(github.router, prefix="/api/v1/github", tags=["GitHub"])
    app.include_router(projects.router, prefix="/api/v1/tenants/{tenant_id}/projects", tags=["Projects"])
    app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])
    app.include_router(ws.router, prefix="/api/v1", tags=["WebSocket"])

    return app


# Create the application instance for ASGI servers
app = create_app()
