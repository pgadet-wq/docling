"""PDF-to-RAG FastAPI Application.

This module provides the main FastAPI application for parsing PDF documents
using IBM Docling and exposing structured content via REST API.
"""

import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.routers import parse_router


def configure_logging() -> None:
    """Configure loguru for structured logging."""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Configure format based on settings
    if settings.log_format == "json":
        log_format = (
            '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
            '"level": "{level.name}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}}}'
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add stderr handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.log_level,
        colorize=settings.log_format != "json",
        serialize=False,
    )

    logger.info(
        "Logging configured",
        level=settings.log_level,
        format=settings.log_format,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown.

    Handles initialization of services and cleanup on shutdown.
    """
    # Startup
    configure_logging()

    settings = get_settings()
    logger.info(
        "Starting PDF-to-RAG API",
        version=settings.app_version,
        use_gpu=settings.use_gpu,
        device=settings.device,
    )

    # Pre-initialize Docling service (optional - lazy init is also fine)
    # Uncomment to warm up models at startup:
    # from app.services.docling_service import get_docling_service
    # _ = get_docling_service().converter

    yield

    # Shutdown
    logger.info("Shutting down PDF-to-RAG API")


# Create FastAPI application
app = FastAPI(
    title="PDF-to-RAG API",
    description="""
    Backend API for parsing PDF documents using IBM Docling.

    ## Features
    - Extract structured content from PDF documents
    - Bounding boxes with normalized coordinates [0-1]
    - Table extraction with cell structure
    - Hierarchical block relationships
    - GPU acceleration support

    ## Usage
    1. Upload a PDF using POST /api/v1/parse
    2. Retrieve parsed content using GET /api/v1/parse/{doc_id}
    3. Query blocks by page using GET /api/v1/parse/{doc_id}/page/{page_num}
    """,
    version=get_settings().app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Middleware to add request timing header."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests."""
    start_time = time.time()

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )

    response = await call_next(request)

    # Log response
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=f"{duration_ms:.2f}",
    )

    return response


# Include routers
app.include_router(parse_router, prefix=settings.api_prefix)


@app.get(
    "/api/v1/health",
    tags=["health"],
    summary="Health check",
    description="Check if the service is running and healthy.",
)
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Health status with version and configuration info.
    """
    settings = get_settings()
    return {
        "status": "healthy",
        "version": settings.app_version,
        "gpu_enabled": settings.use_gpu,
        "device": settings.device,
    }


@app.get(
    "/api/v1/config",
    tags=["config"],
    summary="Get configuration",
    description="Get current API configuration (non-sensitive values only).",
)
async def get_config() -> dict:
    """Get current configuration.

    Returns:
        Non-sensitive configuration values.
    """
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "use_gpu": settings.use_gpu,
        "device": settings.device,
        "max_file_size_mb": settings.max_file_size_mb,
        "allowed_extensions": settings.allowed_extensions,
        "ocr_enabled": settings.docling_ocr_enabled,
        "table_extraction": settings.docling_table_extraction,
        "max_pages": settings.max_pages,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return {"message": "Welcome to PDF-to-RAG API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
