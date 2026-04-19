"""
REALMS API Main Application
Read-only service for spiritual entity knowledge base
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from realms.api.rate_limit import limiter
from realms.api.routes import entities, classes, hierarchy, relationships, cultures, regions, sources, search, stats, metrics, graph, export, review, corroboration
from realms.api.routes.sources import extractions_router

WEB_DIR = Path(os.getenv("REALMS_WEB_DIR", "/app/web"))

app = FastAPI(
    title="REALMS API",
    description="Research Entity Archive for Light & Metaphysical Spirit Hierarchies - Read-only public API",
    version="1.0.0",
    contact={
        "name": "REALMS Project",
        "url": "https://realms.org",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware for public access. Writes are token-gated at the endpoint
# level (see realms/api/dependencies.py); allowing POST/PATCH here just lets
# the in-app UI talk to /review/* and /corroboration/* from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(entities.router, prefix="/entities", tags=["entities"])
app.include_router(classes.router, prefix="/entity-classes", tags=["entity-classes"])
app.include_router(hierarchy.router, prefix="/hierarchy", tags=["hierarchy"])
app.include_router(relationships.router, prefix="/relationships", tags=["relationships"])
app.include_router(cultures.router, prefix="/cultures", tags=["cultures"])
app.include_router(regions.router, prefix="/regions", tags=["regions"])
app.include_router(sources.router, prefix="/sources", tags=["sources"])
app.include_router(extractions_router, prefix="/extractions", tags=["extractions"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(export.router, prefix="/export", tags=["export"])
app.include_router(review.router, prefix="/review", tags=["review"])
app.include_router(corroboration.router, prefix="/corroboration", tags=["corroboration"])


if WEB_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/")
async def root():
    if (WEB_DIR / "index.html").exists():
        return RedirectResponse(url="/app/")
    return {
        "message": "Welcome to REALMS API",
        "description": "Research Entity Archive for Light & Metaphysical Spirit Hierarchies",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "service": "realms-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Make OpenAPI docs available
# FastAPI automatically provides /docs and /redoc endpoints