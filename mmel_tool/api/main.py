"""
MEL/MMEL Audit API

FastAPI application for parsing and auditing MEL vs MMEL compliance.
"""

import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import upload_router, parse_router, audit_router, reports_router, chat_router
from .models.schemas import HealthResponse, ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mmel_api")

# API version
API_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(f"Starting MEL/MMEL Audit API v{API_VERSION}")
    yield
    logger.info("Shutting down MEL/MMEL Audit API")


# Create FastAPI app
app = FastAPI(
    title="MEL/MMEL Audit API",
    description="""
## MEL vs MMEL Conformity Audit System

This API provides endpoints for:
- **Upload**: Upload MMEL and MEL PDF files
- **Parse**: Extract structured data from PDF documents
- **Audit**: Compare MEL against MMEL for compliance
- **Reports**: Generate and download audit reports
- **Items**: Query and filter parsed items

### Compliance Statuses
- **COMPLIANT**: MEL matches MMEL requirements
- **MORE_RESTRICTIVE**: MEL is stricter than MMEL (OK)
- **NON_COMPLIANT**: MEL is less restrictive than MMEL
- **MISSING_IN_MEL**: MMEL item not found in MEL
- **EXTRA_IN_MEL**: MEL item has no MMEL equivalent
    """,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.now()

    response = await call_next(request)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc),
            status_code=500
        ).model_dump()
    )


# Include routers
app.include_router(upload_router, prefix="/api/v1")
app.include_router(parse_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


# Health check endpoint
@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the API status and version.
    """
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        timestamp=datetime.now(),
        services={
            "api": "running",
            "parser": "available",
            "audit": "available",
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "MEL/MMEL Audit API",
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# Quick audit endpoint using default files
@app.post("/api/v1/audit/quick", tags=["Audit"])
async def quick_audit():
    """
    Run a quick audit using the default parsed files.

    Uses:
    - MMEL: output/parsed/mmel_pc12_structured.json
    - MEL: output/parsed/mel_pc12_structured.json
    """
    from .routes.audit import run_audit
    from .models.schemas import AuditRequest

    request = AuditRequest(
        mmel_file="output/parsed/mmel_pc12_structured.json",
        mel_file="output/parsed/mel_pc12_structured.json"
    )

    return await run_audit(request)
