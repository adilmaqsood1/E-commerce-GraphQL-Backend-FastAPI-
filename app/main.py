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
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    try:
        redis = await get_redis()
        await redis.ping()
        print("✅ Redis connected")
    except Exception as exc:
        print(f"⚠️ Redis connection deferred: {exc}")

    print("✅ Application ready")
    yield

    try:
        await close_redis()
    except Exception:
        pass
    try:
        await engine.dispose()
    except Exception:
        pass
    print("👋 Application shut down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="E-Commerce GraphQL Backend — FastAPI + Strawberry + AI Recommendations",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_router, prefix="/graphql")


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
