"""FastAPI application entry point.

Configures lifespan startup hooks, interactive documentation metadata,
error handlers, and route mounts.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.routes import router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager to initialize resources."""
    # Initialize SQLite tables on startup
    init_db()
    yield
    # Cleanup logic (if needed in future)


app = FastAPI(
    title="Cerevyn Solutions PS04 - Azure Support Ticket Automation API",
    description=(
        "Production-ready backend API that accepts customer complaints, classifies "
        "them using explainable deterministic NLP heuristics, assigns priority and "
        "support teams, generates concise summaries and draft responses, and enforces "
        "human-in-the-loop approval before finalizing responses."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router)


STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", summary="Web Dashboard UI", include_in_schema=False)
@app.get("/dashboard", summary="Web Dashboard UI", include_in_schema=False)
def dashboard():
    """Serve the interactive web frontend dashboard."""
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return {
        "message": "Welcome to Cerevyn Solutions PS04 - Azure Support Ticket Automation API",
        "documentation": "/docs",
        "health": "/health",
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=(settings.ENVIRONMENT == "development"),
    )
