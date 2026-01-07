"""Pytest configuration and fixtures for PDF-to-RAG tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.models.document import (
    BoundingBox,
    DocumentBlock,
    PageInfo,
    ParsedDocument,
    TableBlock,
    TableCell,
)


@pytest.fixture
def temp_storage_path() -> Generator[Path, None, None]:
    """Create a temporary directory for test storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_storage_path: Path) -> Settings:
    """Create test settings with temporary storage."""
    return Settings(
        app_name="PDF-to-RAG Test",
        debug=True,
        use_gpu=False,
        device="cpu",
        max_file_size_mb=10,
        storage_path=temp_storage_path,
        log_level="DEBUG",
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create a test client with mocked settings."""
    # Override settings dependency
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client

    # Clear overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_bbox() -> BoundingBox:
    """Create a sample bounding box."""
    return BoundingBox(
        x0=0.1,
        y0=0.2,
        x1=0.9,
        y1=0.3,
        page=1,
    )


@pytest.fixture
def sample_block(sample_bbox: BoundingBox) -> DocumentBlock:
    """Create a sample document block."""
    return DocumentBlock(
        id="test-block-1",
        type="paragraph",
        text="This is a sample paragraph.",
        bbox=sample_bbox,
        confidence=0.95,
    )


@pytest.fixture
def sample_table_block() -> TableBlock:
    """Create a sample table block."""
    return TableBlock(
        id="test-table-1",
        type="table",
        text="Header 1 | Header 2 | Value 1 | Value 2",
        bbox=BoundingBox(x0=0.1, y0=0.4, x1=0.9, y1=0.6, page=1),
        rows=2,
        cols=2,
        cells=[
            TableCell(row=0, col=0, text="Header 1", is_header=True),
            TableCell(row=0, col=1, text="Header 2", is_header=True),
            TableCell(row=1, col=0, text="Value 1", is_header=False),
            TableCell(row=1, col=1, text="Value 2", is_header=False),
        ],
    )


@pytest.fixture
def sample_parsed_document(
    sample_block: DocumentBlock,
    sample_table_block: TableBlock,
) -> ParsedDocument:
    """Create a sample parsed document."""
    return ParsedDocument(
        id="test-doc-1",
        filename="test.pdf",
        total_pages=1,
        blocks=[sample_block, sample_table_block],
        pages=[PageInfo(page_number=1, width=612.0, height=792.0, block_count=2)],
        metadata={"title": "Test Document"},
        processing_time_ms=100,
    )


@pytest.fixture
def simple_pdf_bytes() -> bytes:
    """Create a minimal valid PDF for testing.

    This creates a simple single-page PDF with text content.
    """
    # Minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000359 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
434
%%EOF"""
    return pdf_content


@pytest.fixture
def invalid_pdf_bytes() -> bytes:
    """Create invalid PDF bytes for testing error handling."""
    return b"This is not a valid PDF file"


@pytest.fixture
def mock_docling_service():
    """Create a mock DoclingService for testing without actual PDF parsing."""
    with patch("app.routers.parse.get_docling_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service
