"""IOSA Configuration Module
============================

Configuration classes for IOSA document parsing.
"""

from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """Supported compute devices."""

    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"  # Apple Silicon
    XPU = "xpu"  # Intel GPU


class TableMode(str, Enum):
    """Table extraction mode."""

    STANDARD = "standard"  # TableFormer (fast)
    VLM = "vlm"  # Vision Language Model (precise)
    HYBRID = "hybrid"  # Auto-detect and use VLM for complex tables


class OutputFormat(str, Enum):
    """Supported output formats."""

    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    CHUNKS = "chunks"  # For RAG
    ALL = "all"


class IOSAConfig(BaseModel):
    """Configuration for IOSA document parsing.

    Attributes:
        vlm_model: HuggingFace model ID for VLM table extraction
        device: Compute device (cuda, cpu, mps, xpu)
        batch_size: Number of pages to process in parallel
        table_mode: How to handle table extraction
        output_formats: List of output formats to generate
        enable_chunking: Whether to generate chunks for RAG
        chunk_size: Target size for chunks (tokens)
        chunk_overlap: Overlap between chunks (tokens)
        extract_standards: Whether to extract IOSA standard codes
        standard_codes: List of standard codes to extract (empty = all)
        cache_dir: Directory for model cache
        artifacts_path: Path for Docling artifacts
        enable_ocr: Whether to enable OCR for scanned documents
        ocr_engine: OCR engine to use
        images_scale: Scale factor for page images
        max_concurrent_pages: Maximum pages to process concurrently
        api_concurrency: Concurrency for API-based VLM
        timeout_per_page: Timeout per page in seconds
    """

    # Model configuration
    vlm_model: str = Field(
        default="pgadet-wq/granite-docling-258M",
        description="HuggingFace model ID for VLM table extraction",
    )
    device: DeviceType = Field(
        default=DeviceType.CUDA,
        description="Compute device for model inference",
    )
    batch_size: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of pages to process in parallel",
    )

    # Pipeline configuration
    table_mode: TableMode = Field(
        default=TableMode.HYBRID,
        description="Table extraction strategy",
    )
    enable_ocr: bool = Field(
        default=True,
        description="Enable OCR for scanned documents",
    )
    ocr_engine: Literal["rapidocr", "tesseract", "easyocr"] = Field(
        default="rapidocr",
        description="OCR engine to use",
    )
    images_scale: float = Field(
        default=2.0,
        ge=1.0,
        le=4.0,
        description="Scale factor for page images",
    )

    # Output configuration
    output_formats: List[OutputFormat] = Field(
        default=[OutputFormat.JSON, OutputFormat.MARKDOWN],
        description="Output formats to generate",
    )
    enable_chunking: bool = Field(
        default=True,
        description="Generate chunks for LLM/RAG",
    )
    chunk_size: int = Field(
        default=512,
        ge=128,
        le=4096,
        description="Target chunk size in tokens",
    )
    chunk_overlap: int = Field(
        default=64,
        ge=0,
        le=512,
        description="Overlap between chunks in tokens",
    )

    # IOSA-specific configuration
    extract_standards: bool = Field(
        default=True,
        description="Extract IOSA standard codes",
    )
    standard_codes: List[str] = Field(
        default=[],
        description="Standard codes to extract (empty = all)",
    )

    # Resource configuration
    cache_dir: Optional[Path] = Field(
        default=None,
        description="Directory for model cache",
    )
    artifacts_path: Optional[Path] = Field(
        default=None,
        description="Path for Docling artifacts",
    )
    max_concurrent_pages: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Maximum pages to process concurrently",
    )
    api_concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Concurrency for API-based VLM",
    )
    timeout_per_page: float = Field(
        default=60.0,
        ge=10.0,
        le=300.0,
        description="Timeout per page in seconds",
    )

    # GPU memory optimization
    gpu_memory_utilization: float = Field(
        default=0.8,
        ge=0.3,
        le=0.95,
        description="GPU memory utilization target",
    )
    max_model_len: int = Field(
        default=8192,
        ge=1024,
        le=32768,
        description="Maximum model context length",
    )

    class Config:
        use_enum_values = True


class APIConfig(BaseModel):
    """Configuration for FastAPI service.

    Attributes:
        host: API host address
        port: API port
        workers: Number of worker processes
        max_upload_size: Maximum file upload size in MB
        enable_cors: Enable CORS
        cors_origins: Allowed CORS origins
        api_key: Optional API key for authentication
        enable_metrics: Enable Prometheus metrics
        log_level: Logging level
    """

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, ge=1, le=65535, description="API port")
    workers: int = Field(default=1, ge=1, le=16, description="Worker processes")
    max_upload_size: int = Field(
        default=100, ge=1, le=1000, description="Max upload size in MB"
    )
    enable_cors: bool = Field(default=True, description="Enable CORS")
    cors_origins: List[str] = Field(default=["*"], description="CORS origins")
    api_key: Optional[str] = Field(default=None, description="API key")
    enable_metrics: bool = Field(default=True, description="Enable metrics")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Log level"
    )


# Default configurations for different deployment scenarios
DEVELOPMENT_CONFIG = IOSAConfig(
    device=DeviceType.CPU,
    batch_size=1,
    table_mode=TableMode.STANDARD,
    max_concurrent_pages=2,
)

PRODUCTION_GPU_CONFIG = IOSAConfig(
    device=DeviceType.CUDA,
    batch_size=4,
    table_mode=TableMode.HYBRID,
    max_concurrent_pages=8,
    gpu_memory_utilization=0.85,
)

HIGH_ACCURACY_CONFIG = IOSAConfig(
    device=DeviceType.CUDA,
    batch_size=2,
    table_mode=TableMode.VLM,
    max_concurrent_pages=4,
    images_scale=2.5,
)
