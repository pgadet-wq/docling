"""IOSA FastAPI Service
======================

REST API for IOSA document parsing.

Endpoints:
- POST /parse: Parse a PDF document
- POST /parse/url: Parse a PDF from URL
- GET /health: Health check
- GET /stats: Parser statistics

Run with:
    uvicorn docling.iosa.api:app --host 0.0.0.0 --port 8000
"""

import hashlib
import logging
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl

_log = logging.getLogger(__name__)

# FastAPI imports (with fallback for when not installed)
try:
    from fastapi import (
        BackgroundTasks,
        FastAPI,
        File,
        Form,
        HTTPException,
        Query,
        UploadFile,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    import uvicorn

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    _log.warning("FastAPI not installed. Install with: pip install fastapi uvicorn python-multipart")

from docling.iosa.config import APIConfig, IOSAConfig, OutputFormat, TableMode
from docling.iosa.models import (
    ChunkMetadata,
    ComplianceItem,
    IOSAChunk,
    IOSADocument,
    IOSAParseResult,
)
from docling.iosa.parser import IOSAParser


# ============================================================================
# Request/Response Models
# ============================================================================


class ParseRequest(BaseModel):
    """Request model for parsing configuration."""

    table_mode: str = Field(default="hybrid", description="Table extraction mode")
    enable_ocr: bool = Field(default=True, description="Enable OCR")
    extract_standards: bool = Field(default=True, description="Extract IOSA standards")
    enable_chunking: bool = Field(default=True, description="Generate chunks")
    chunk_size: int = Field(default=512, ge=128, le=4096, description="Chunk size")
    output_formats: List[str] = Field(
        default=["json", "markdown"],
        description="Output formats to generate",
    )


class ParseURLRequest(BaseModel):
    """Request model for URL-based parsing."""

    url: HttpUrl
    config: Optional[ParseRequest] = None


class ChunkResponse(BaseModel):
    """Response model for a chunk."""

    content: str
    metadata: ChunkMetadata


class ComplianceItemResponse(BaseModel):
    """Response model for compliance items."""

    standard_code: str
    reference_number: str
    requirement_text: str
    priority: Optional[str] = None
    page_references: List[int] = []


class ParseResponse(BaseModel):
    """Response model for parsing results."""

    success: bool
    document_id: str
    filename: str
    total_pages: int
    processing_time_seconds: float
    table_count: int
    chunk_count: int
    compliance_items_count: int
    standard_codes_found: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []


class DetailedParseResponse(ParseResponse):
    """Detailed response including content."""

    markdown: Optional[str] = None
    chunks: Optional[List[ChunkResponse]] = None
    compliance_items: Optional[List[ComplianceItemResponse]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str
    gpu_available: bool
    models_loaded: bool


class StatsResponse(BaseModel):
    """Statistics response."""

    documents_processed: int
    total_pages_processed: int
    total_tables_extracted: int
    total_chunks_created: int
    average_processing_time: float
    uptime_seconds: float


# ============================================================================
# Service State
# ============================================================================


class ServiceState:
    """Global service state."""

    def __init__(self):
        self.parser: Optional[IOSAParser] = None
        self.config: IOSAConfig = IOSAConfig()
        self.api_config: APIConfig = APIConfig()
        self.start_time: float = time.time()

        # Statistics
        self.documents_processed: int = 0
        self.total_pages: int = 0
        self.total_tables: int = 0
        self.total_chunks: int = 0
        self.total_processing_time: float = 0.0

        # Temp directory for uploads
        self.temp_dir: Optional[Path] = None

    def initialize(self, config: Optional[IOSAConfig] = None):
        """Initialize the service."""
        if config:
            self.config = config

        self.parser = IOSAParser(config=self.config)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="iosa_"))
        _log.info(f"Service initialized. Temp dir: {self.temp_dir}")

    def cleanup(self):
        """Cleanup resources."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        _log.info("Service cleaned up")

    def update_stats(self, result: IOSAParseResult):
        """Update statistics from parse result."""
        self.documents_processed += 1
        if result.document:
            self.total_pages += result.document.metadata.total_pages
            self.total_tables += result.document.metadata.table_count
        self.total_chunks += len(result.chunks)
        if result.processing_stats:
            self.total_processing_time += result.processing_stats.get(
                "processing_time_seconds", 0
            )


# Global state
state = ServiceState()


# ============================================================================
# FastAPI Application
# ============================================================================

if FASTAPI_AVAILABLE:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager."""
        # Startup
        _log.info("Starting IOSA API service...")
        state.initialize()
        yield
        # Shutdown
        _log.info("Shutting down IOSA API service...")
        state.cleanup()

    app = FastAPI(
        title="IOSA Document Parser API",
        description="REST API for parsing IOSA aviation documents with hybrid pipeline",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========================================================================
    # Endpoints
    # ========================================================================

    @app.get("/", response_model=Dict[str, str])
    async def root():
        """Root endpoint."""
        return {
            "service": "IOSA Document Parser",
            "version": "1.0.0",
            "docs": "/docs",
        }

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        import torch

        gpu_available = torch.cuda.is_available() if hasattr(torch, "cuda") else False

        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            gpu_available=gpu_available,
            models_loaded=state.parser is not None,
        )

    @app.get("/stats", response_model=StatsResponse)
    async def get_stats():
        """Get service statistics."""
        avg_time = 0.0
        if state.documents_processed > 0:
            avg_time = state.total_processing_time / state.documents_processed

        return StatsResponse(
            documents_processed=state.documents_processed,
            total_pages_processed=state.total_pages,
            total_tables_extracted=state.total_tables,
            total_chunks_created=state.total_chunks,
            average_processing_time=avg_time,
            uptime_seconds=time.time() - state.start_time,
        )

    @app.post("/parse", response_model=ParseResponse)
    async def parse_document(
        file: UploadFile = File(...),
        table_mode: str = Form(default="hybrid"),
        enable_ocr: bool = Form(default=True),
        extract_standards: bool = Form(default=True),
        enable_chunking: bool = Form(default=True),
        chunk_size: int = Form(default=512),
    ):
        """Parse an uploaded PDF document.

        Args:
            file: PDF file to parse
            table_mode: Table extraction mode (standard/vlm/hybrid)
            enable_ocr: Enable OCR for scanned documents
            extract_standards: Extract IOSA standard codes
            enable_chunking: Generate chunks for RAG
            chunk_size: Target chunk size in tokens

        Returns:
            ParseResponse with parsing results
        """
        if state.parser is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Save uploaded file
        if state.temp_dir is None:
            state.temp_dir = Path(tempfile.mkdtemp(prefix="iosa_"))

        file_path = state.temp_dir / f"{hashlib.md5(file.filename.encode()).hexdigest()}.pdf"

        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Create config for this request
            config = IOSAConfig(
                table_mode=TableMode(table_mode),
                enable_ocr=enable_ocr,
                extract_standards=extract_standards,
                enable_chunking=enable_chunking,
                chunk_size=chunk_size,
            )

            # Parse document
            parser = IOSAParser(config=config)
            result = parser.parse(file_path)

            # Update stats
            state.update_stats(result)

            if not result.success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Parsing failed: {result.errors}",
                )

            return ParseResponse(
                success=True,
                document_id=result.document.metadata.document_id if result.document else "",
                filename=file.filename or "",
                total_pages=result.document.metadata.total_pages if result.document else 0,
                processing_time_seconds=result.processing_stats.get("processing_time_seconds", 0),
                table_count=result.document.metadata.table_count if result.document else 0,
                chunk_count=len(result.chunks),
                compliance_items_count=len(result.document.compliance_items) if result.document else 0,
                standard_codes_found=[
                    s.value for s in result.document.metadata.standard_codes_found
                ] if result.document else [],
                errors=result.errors,
                warnings=result.warnings,
            )

        finally:
            # Cleanup temp file
            if file_path.exists():
                file_path.unlink()

    @app.post("/parse/detailed", response_model=DetailedParseResponse)
    async def parse_document_detailed(
        file: UploadFile = File(...),
        table_mode: str = Form(default="hybrid"),
        enable_ocr: bool = Form(default=True),
        extract_standards: bool = Form(default=True),
        enable_chunking: bool = Form(default=True),
        chunk_size: int = Form(default=512),
        include_markdown: bool = Form(default=True),
        include_chunks: bool = Form(default=True),
        include_compliance: bool = Form(default=True),
    ):
        """Parse document with detailed response including content.

        Returns markdown, chunks, and compliance items in response.
        """
        if state.parser is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Save uploaded file
        if state.temp_dir is None:
            state.temp_dir = Path(tempfile.mkdtemp(prefix="iosa_"))

        file_path = state.temp_dir / f"{hashlib.md5(file.filename.encode()).hexdigest()}.pdf"

        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Create config
            config = IOSAConfig(
                table_mode=TableMode(table_mode),
                enable_ocr=enable_ocr,
                extract_standards=extract_standards,
                enable_chunking=enable_chunking,
                chunk_size=chunk_size,
            )

            # Parse
            parser = IOSAParser(config=config)
            result = parser.parse(file_path)
            state.update_stats(result)

            if not result.success or result.document is None:
                raise HTTPException(
                    status_code=500,
                    detail=f"Parsing failed: {result.errors}",
                )

            # Build response
            response = DetailedParseResponse(
                success=True,
                document_id=result.document.metadata.document_id,
                filename=file.filename or "",
                total_pages=result.document.metadata.total_pages,
                processing_time_seconds=result.processing_stats.get("processing_time_seconds", 0),
                table_count=result.document.metadata.table_count,
                chunk_count=len(result.chunks),
                compliance_items_count=len(result.document.compliance_items),
                standard_codes_found=[s.value for s in result.document.metadata.standard_codes_found],
                errors=result.errors,
                warnings=result.warnings,
            )

            if include_markdown:
                response.markdown = result.document.markdown

            if include_chunks and result.chunks:
                response.chunks = [
                    ChunkResponse(content=c.content, metadata=c.metadata)
                    for c in result.chunks[:100]  # Limit chunks in response
                ]

            if include_compliance and result.document.compliance_items:
                response.compliance_items = [
                    ComplianceItemResponse(
                        standard_code=item.standard_code.value,
                        reference_number=item.reference_number,
                        requirement_text=item.requirement_text[:500],
                        priority=item.priority,
                        page_references=item.page_references,
                    )
                    for item in result.document.compliance_items[:100]
                ]

            return response

        finally:
            if file_path.exists():
                file_path.unlink()

    @app.post("/parse/url", response_model=ParseResponse)
    async def parse_document_from_url(request: ParseURLRequest):
        """Parse a PDF document from URL.

        Downloads the PDF and parses it.
        """
        import httpx

        if state.parser is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Download file
        if state.temp_dir is None:
            state.temp_dir = Path(tempfile.mkdtemp(prefix="iosa_"))

        url_hash = hashlib.md5(str(request.url).encode()).hexdigest()
        file_path = state.temp_dir / f"{url_hash}.pdf"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(str(request.url))
                response.raise_for_status()

                with open(file_path, "wb") as f:
                    f.write(response.content)

            # Create config
            config = IOSAConfig()
            if request.config:
                config = IOSAConfig(
                    table_mode=TableMode(request.config.table_mode),
                    enable_ocr=request.config.enable_ocr,
                    extract_standards=request.config.extract_standards,
                    enable_chunking=request.config.enable_chunking,
                    chunk_size=request.config.chunk_size,
                )

            # Parse
            parser = IOSAParser(config=config)
            result = parser.parse(file_path)
            state.update_stats(result)

            if not result.success or result.document is None:
                raise HTTPException(
                    status_code=500,
                    detail=f"Parsing failed: {result.errors}",
                )

            return ParseResponse(
                success=True,
                document_id=result.document.metadata.document_id,
                filename=file_path.name,
                total_pages=result.document.metadata.total_pages,
                processing_time_seconds=result.processing_stats.get("processing_time_seconds", 0),
                table_count=result.document.metadata.table_count,
                chunk_count=len(result.chunks),
                compliance_items_count=len(result.document.compliance_items),
                standard_codes_found=[s.value for s in result.document.metadata.standard_codes_found],
                errors=result.errors,
                warnings=result.warnings,
            )

        except httpx.HTTPError as e:
            raise HTTPException(status_code=400, detail=f"Failed to download URL: {e}")

        finally:
            if file_path.exists():
                file_path.unlink()

    @app.get("/config")
    async def get_config():
        """Get current parser configuration."""
        return state.config.model_dump()

    @app.post("/config")
    async def update_config(config: IOSAConfig):
        """Update parser configuration."""
        state.config = config
        state.parser = IOSAParser(config=config)
        return {"status": "updated", "config": config.model_dump()}


# ============================================================================
# Server Runner
# ============================================================================


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = 1,
    reload: bool = False,
    config: Optional[IOSAConfig] = None,
):
    """Run the FastAPI server.

    Args:
        host: Host to bind to
        port: Port to bind to
        workers: Number of workers
        reload: Enable auto-reload
        config: Optional IOSA configuration
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is not installed. Install with: pip install fastapi uvicorn python-multipart"
        )

    if config:
        state.config = config

    uvicorn.run(
        "docling.iosa.api:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
