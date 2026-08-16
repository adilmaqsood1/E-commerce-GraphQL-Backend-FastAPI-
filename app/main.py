"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.redis import close_redis, get_redis
from app.graphql_app import graphql_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────────
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    # Warm up Redis connection
    redis = await get_redis()
    await redis.ping()
    print("✅ Redis connected")

    # Note: Run `alembic upgrade head` separately (or in Dockerfile CMD)
    print("✅ Application ready")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await close_redis()
    await engine.dispose()
    print("👋 Application shut down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="E-Commerce GraphQL Backend — FastAPI + Strawberry + AI Recommendations",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GraphQL endpoint ──────────────────────────────────────────────────────────
app.include_router(graphql_router, prefix="/graphql")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return JSONResponse(
        {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.app_env,
        }
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "graphql": "/graphql",
        "health": "/health",
        "docs": "/docs",
    }
