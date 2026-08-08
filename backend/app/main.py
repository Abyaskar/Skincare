"""
FastAPI application entry point.

Lifecycle:
- Startup: logging, MongoDB connection, index creation, FAISS load
- Shutdown: MongoDB disconnect
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_vector_store
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import MongoDB
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.product_repository import ProductRepository

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    setup_logging()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    await MongoDB.connect()
    db = MongoDB.get_database()

    product_repo = ProductRepository(db)
    feedback_repo = FeedbackRepository(db)
    history_repo = HistoryRepository(db)
    await product_repo.ensure_indexes()
    await feedback_repo.ensure_indexes()
    await history_repo.ensure_indexes()

    vector_store = get_vector_store()
    if vector_store.is_loaded:
        logger.info("FAISS index ready: %d vectors", vector_store.size)
    else:
        logger.warning(
            "FAISS index not found. Run: python scripts/ingest_data.py"
        )

    yield

    await MongoDB.disconnect()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Production-ready AI Beauty Recommendation Engine with "
        "content-based, semantic, and hybrid recommendations, plus RAG chat."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check for load balancers and monitoring."""
    vector_store = get_vector_store()
    product_count = 0
    try:
        db = MongoDB.get_database()
        product_count = await ProductRepository(db).count()
    except Exception:
        pass

    return {
        "status": "healthy",
        "version": settings.app_version,
        "mongodb": MongoDB.db is not None,
        "faiss_loaded": vector_store.is_loaded,
        "faiss_vectors": vector_store.size,
        "products_in_db": product_count,
    }


# Mount API routes at root (matches spec: POST /recommend, GET /products, etc.)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
