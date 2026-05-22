"""
FastAPI application entrypoint for the RAG backend.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.upload_routes import router as upload_router
from app.api.routes.chat_routes import router as chat_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.documents_routes import router as documents_router
from app.api.routes.chat_history_routes import router as chat_history_router
from app.api.routes.collections_routes import router as collections_router
from app.api.routes.settings_routes import router as settings_router
from app.api.routes.queue_routes import router as queue_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logging."""
    logger.info("Starting application %s v%s", settings.APP_NAME, settings.API_VERSION)
    logger.info("Debug mode: %s", settings.DEBUG)
    logger.info("Environment: %s", "development" if settings.DEBUG else "production")
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception: %s", str(exc))
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "details": None})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


app.include_router(upload_router,        prefix=f"/api/{settings.API_VERSION}")
app.include_router(chat_router,          prefix=f"/api/{settings.API_VERSION}")
app.include_router(auth_router,          prefix=f"/api/{settings.API_VERSION}")
app.include_router(documents_router,     prefix=f"/api/{settings.API_VERSION}")
app.include_router(chat_history_router,  prefix=f"/api/{settings.API_VERSION}")
app.include_router(collections_router,   prefix=f"/api/{settings.API_VERSION}")
app.include_router(settings_router,      prefix=f"/api/{settings.API_VERSION}")
app.include_router(queue_router,         prefix=f"/api/{settings.API_VERSION}")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return JSONResponse(status_code=204, content=None)


@app.get("/", include_in_schema=True)
async def root() -> dict:
    return {
        "status": "operational",
        "app_name": settings.APP_NAME,
        "api_version": settings.API_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health", include_in_schema=True)
async def health_check() -> dict:
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "api_version": settings.API_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["app"]
