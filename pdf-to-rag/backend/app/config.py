"""Application configuration using Pydantic Settings.

This module provides centralized configuration management with
environment variable support and validation.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables.
    Environment variables should be uppercase with underscores.

    Example:
        USE_GPU=true python -m app.main
    """

    # Application metadata
    app_name: str = Field(default="PDF-to-RAG API", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # GPU/CPU Configuration
    use_gpu: bool = Field(
        default=False,
        description="Enable GPU acceleration (requires CUDA)",
    )
    device: Literal["cpu", "cuda", "mps"] = Field(
        default="cpu",
        description="Device to use for inference",
    )

    # File handling
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum upload file size in MB",
    )
    allowed_extensions: list[str] = Field(
        default=[".pdf"],
        description="Allowed file extensions",
    )

    # Storage
    storage_path: Path = Field(
        default=Path("/app/storage"),
        description="Path for storing parsed documents",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=0,
        description="Cache TTL for parsed documents (0 = no cache)",
    )

    # Docling configuration
    docling_ocr_enabled: bool = Field(
        default=True,
        description="Enable OCR for scanned documents",
    )
    docling_table_extraction: bool = Field(
        default=True,
        description="Enable TableFormer for table extraction",
    )
    docling_image_extraction: bool = Field(
        default=True,
        description="Extract image metadata",
    )

    # Processing limits
    max_pages: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of pages to process",
    )
    processing_timeout_seconds: int = Field(
        default=600,
        ge=60,
        description="Maximum processing time per document",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)",
    )

    # API Configuration
    api_prefix: str = Field(
        default="/api/v1",
        description="API route prefix",
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )

    @field_validator("device", mode="before")
    @classmethod
    def validate_device(cls, v: str, info) -> str:
        """Auto-detect device based on USE_GPU setting."""
        if v == "cpu":
            # Check if GPU is requested via use_gpu
            use_gpu = info.data.get("use_gpu", False)
            if use_gpu:
                # Try to detect available GPU
                try:
                    import torch

                    if torch.cuda.is_available():
                        return "cuda"
                    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                        return "mps"
                except ImportError:
                    pass
        return v

    @field_validator("storage_path", mode="before")
    @classmethod
    def ensure_storage_path(cls, v: str | Path) -> Path:
        """Ensure storage path exists."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def is_extension_allowed(self, filename: str) -> bool:
        """Check if file extension is allowed.

        Args:
            filename: Name of the file to check

        Returns:
            True if extension is allowed
        """
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.allowed_extensions

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns:
        Settings instance (cached)
    """
    return Settings()


# Convenience function for dependency injection
def get_settings_dependency() -> Settings:
    """Get settings for FastAPI dependency injection.

    Returns:
        Settings instance
    """
    return get_settings()
