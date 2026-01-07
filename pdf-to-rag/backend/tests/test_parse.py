"""Tests for PDF parsing endpoints and services.

This module contains comprehensive tests for:
- PDF upload and parsing
- Document retrieval
- Block querying by page
- Error handling
- Bounding box validation
- Table extraction
"""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.document import (
    BoundingBox,
    DocumentBlock,
    PageInfo,
    ParsedDocument,
    TableBlock,
    TableCell,
)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient):
        """Health check should return healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "gpu_enabled" in data
        assert "device" in data

    def test_health_check_includes_timing_header(self, client: TestClient):
        """Health check response should include timing header."""
        response = client.get("/api/v1/health")

        assert "X-Process-Time" in response.headers


class TestConfigEndpoint:
    """Tests for configuration endpoint."""

    def test_get_config_returns_settings(self, client: TestClient):
        """Config endpoint should return non-sensitive settings."""
        response = client.get("/api/v1/config")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "app_name" in data
        assert "max_file_size_mb" in data
        assert "allowed_extensions" in data
        assert "device" in data


class TestBoundingBoxModel:
    """Tests for BoundingBox Pydantic model."""

    def test_valid_bounding_box(self):
        """Valid bounding box should be created successfully."""
        bbox = BoundingBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8, page=1)

        assert bbox.x0 == 0.1
        assert bbox.y0 == 0.2
        assert bbox.x1 == 0.9
        assert bbox.y1 == 0.8
        assert bbox.page == 1

    def test_bounding_box_normalized_values(self):
        """Bounding box values should be between 0 and 1."""
        with pytest.raises(ValueError):
            BoundingBox(x0=-0.1, y0=0.2, x1=0.9, y1=0.8, page=1)

        with pytest.raises(ValueError):
            BoundingBox(x0=0.1, y0=0.2, x1=1.5, y1=0.8, page=1)

    def test_bounding_box_x1_greater_than_x0(self):
        """x1 should be greater than or equal to x0."""
        with pytest.raises(ValueError):
            BoundingBox(x0=0.9, y0=0.2, x1=0.1, y1=0.8, page=1)

    def test_bounding_box_y1_greater_than_y0(self):
        """y1 should be greater than or equal to y0."""
        with pytest.raises(ValueError):
            BoundingBox(x0=0.1, y0=0.8, x1=0.9, y1=0.2, page=1)

    def test_bounding_box_page_positive(self):
        """Page number should be positive."""
        with pytest.raises(ValueError):
            BoundingBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8, page=0)

    def test_bounding_box_width_property(self, sample_bbox: BoundingBox):
        """Width property should calculate correctly."""
        assert sample_bbox.width == pytest.approx(0.8, rel=0.01)

    def test_bounding_box_height_property(self, sample_bbox: BoundingBox):
        """Height property should calculate correctly."""
        assert sample_bbox.height == pytest.approx(0.1, rel=0.01)

    def test_bounding_box_area_property(self, sample_bbox: BoundingBox):
        """Area property should calculate correctly."""
        expected_area = 0.8 * 0.1  # width * height
        assert sample_bbox.area == pytest.approx(expected_area, rel=0.01)


class TestDocumentBlockModel:
    """Tests for DocumentBlock Pydantic model."""

    def test_valid_document_block(self, sample_bbox: BoundingBox):
        """Valid document block should be created successfully."""
        block = DocumentBlock(
            type="paragraph",
            text="Sample text",
            bbox=sample_bbox,
        )

        assert block.type == "paragraph"
        assert block.text == "Sample text"
        assert block.id is not None  # UUID auto-generated
        assert block.confidence == 1.0  # Default value
        assert block.hidden is False  # Default value

    def test_document_block_with_all_fields(self, sample_bbox: BoundingBox):
        """Document block with all optional fields."""
        block = DocumentBlock(
            id="custom-id",
            type="title",
            text="Chapter 1",
            bbox=sample_bbox,
            level=1,
            parent_id="parent-id",
            children_ids=["child-1", "child-2"],
            confidence=0.95,
            metadata={"source": "ocr"},
            hidden=False,
            keep_with_next=True,
        )

        assert block.id == "custom-id"
        assert block.level == 1
        assert block.parent_id == "parent-id"
        assert len(block.children_ids) == 2
        assert block.keep_with_next is True


class TestTableBlockModel:
    """Tests for TableBlock Pydantic model."""

    def test_valid_table_block(self, sample_bbox: BoundingBox):
        """Valid table block should be created successfully."""
        cells = [
            TableCell(row=0, col=0, text="A1"),
            TableCell(row=0, col=1, text="B1"),
            TableCell(row=1, col=0, text="A2"),
            TableCell(row=1, col=1, text="B2"),
        ]

        table = TableBlock(
            type="table",
            text="A1 | B1 | A2 | B2",
            bbox=sample_bbox,
            rows=2,
            cols=2,
            cells=cells,
        )

        assert table.type == "table"
        assert table.rows == 2
        assert table.cols == 2
        assert len(table.cells) == 4

    def test_table_cell_with_span(self):
        """Table cell with row and column span."""
        cell = TableCell(
            row=0,
            col=0,
            row_span=2,
            col_span=3,
            text="Merged cell",
            is_header=True,
        )

        assert cell.row_span == 2
        assert cell.col_span == 3
        assert cell.is_header is True


class TestParsedDocumentModel:
    """Tests for ParsedDocument Pydantic model."""

    def test_valid_parsed_document(
        self,
        sample_block: DocumentBlock,
        sample_table_block: TableBlock,
    ):
        """Valid parsed document should be created successfully."""
        doc = ParsedDocument(
            filename="test.pdf",
            total_pages=2,
            blocks=[sample_block, sample_table_block],
            processing_time_ms=150,
        )

        assert doc.filename == "test.pdf"
        assert doc.total_pages == 2
        assert len(doc.blocks) == 2
        assert doc.id is not None
        assert doc.created_at is not None

    def test_get_blocks_by_page(self, sample_parsed_document: ParsedDocument):
        """Get blocks by page should filter correctly."""
        page_1_blocks = sample_parsed_document.get_blocks_by_page(1)
        assert len(page_1_blocks) == 2

        page_2_blocks = sample_parsed_document.get_blocks_by_page(2)
        assert len(page_2_blocks) == 0

    def test_get_blocks_by_type(self, sample_parsed_document: ParsedDocument):
        """Get blocks by type should filter correctly."""
        tables = sample_parsed_document.get_blocks_by_type("table")
        assert len(tables) == 1
        assert tables[0].type == "table"

        paragraphs = sample_parsed_document.get_blocks_by_type("paragraph")
        assert len(paragraphs) == 1

    def test_table_count_property(self, sample_parsed_document: ParsedDocument):
        """Table count property should return correct count."""
        assert sample_parsed_document.table_count == 1

    def test_visible_blocks_property(self, sample_parsed_document: ParsedDocument):
        """Visible blocks should exclude hidden blocks."""
        # All blocks visible initially
        assert len(sample_parsed_document.visible_blocks) == 2

        # Hide one block
        sample_parsed_document.blocks[0].hidden = True
        assert len(sample_parsed_document.visible_blocks) == 1


class TestParseEndpoint:
    """Tests for PDF parsing endpoint."""

    def test_parse_invalid_extension(self, client: TestClient):
        """Uploading non-PDF file should return 400."""
        response = client.post(
            "/api/v1/parse",
            files={"file": ("test.txt", b"Hello World", "text/plain")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not allowed" in response.json()["detail"].lower()

    def test_parse_empty_filename(self, client: TestClient):
        """Uploading file without filename should return 400."""
        response = client.post(
            "/api/v1/parse",
            files={"file": ("", b"content", "application/pdf")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_parse_invalid_pdf_content(
        self,
        client: TestClient,
        invalid_pdf_bytes: bytes,
    ):
        """Uploading invalid PDF content should return 400."""
        response = client.post(
            "/api/v1/parse",
            files={"file": ("test.pdf", invalid_pdf_bytes, "application/pdf")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in response.json()["detail"].lower()

    def test_parse_file_too_large(self, client: TestClient, test_settings):
        """Uploading file exceeding size limit should return 413."""
        # Create content larger than max size
        large_content = b"%PDF-" + (b"x" * (test_settings.max_file_size_bytes + 1000))

        response = client.post(
            "/api/v1/parse",
            files={"file": ("large.pdf", large_content, "application/pdf")},
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "too large" in response.json()["detail"].lower()

    def test_parse_success_with_mock(
        self,
        client: TestClient,
        simple_pdf_bytes: bytes,
        sample_parsed_document: ParsedDocument,
    ):
        """Successful PDF parsing should return ParsedDocument."""
        with patch("app.routers.parse.get_docling_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.parse_pdf.return_value = sample_parsed_document
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/v1/parse",
                files={"file": ("test.pdf", simple_pdf_bytes, "application/pdf")},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            assert data["document"]["filename"] == "test.pdf"
            assert "blocks" in data["document"]


class TestGetDocumentEndpoint:
    """Tests for document retrieval endpoint."""

    def test_get_nonexistent_document(self, client: TestClient):
        """Getting non-existent document should return 404."""
        response = client.get("/api/v1/parse/nonexistent-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_document_success(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Getting existing document should return document."""
        # Save document to cache
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        response = client.get(f"/api/v1/parse/{sample_parsed_document.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_parsed_document.id
        assert data["filename"] == sample_parsed_document.filename


class TestGetPageBlocksEndpoint:
    """Tests for page blocks retrieval endpoint."""

    def test_get_page_blocks_nonexistent_doc(self, client: TestClient):
        """Getting blocks for non-existent document should return 404."""
        response = client.get("/api/v1/parse/nonexistent-id/page/1")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_page_blocks_invalid_page(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Getting blocks for invalid page should return 400."""
        # Save document to cache
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        # Page 0 is invalid
        response = client.get(f"/api/v1/parse/{sample_parsed_document.id}/page/0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Page 100 exceeds total pages
        response = client.get(f"/api/v1/parse/{sample_parsed_document.id}/page/100")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_page_blocks_success(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Getting blocks for valid page should return blocks."""
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        response = client.get(f"/api/v1/parse/{sample_parsed_document.id}/page/1")

        assert response.status_code == status.HTTP_200_OK
        blocks = response.json()
        assert len(blocks) == 2


class TestBlocksFilterEndpoint:
    """Tests for blocks filtering endpoint."""

    def test_filter_by_type(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Filtering blocks by type should work correctly."""
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        response = client.get(
            f"/api/v1/parse/{sample_parsed_document.id}/blocks",
            params={"block_type": "table"},
        )

        assert response.status_code == status.HTTP_200_OK
        blocks = response.json()
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"


class TestDeleteDocumentEndpoint:
    """Tests for document deletion endpoint."""

    def test_delete_nonexistent_document(self, client: TestClient):
        """Deleting non-existent document should return 404."""
        response = client.delete("/api/v1/parse/nonexistent-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_document_success(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Deleting existing document should succeed."""
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        response = client.delete(f"/api/v1/parse/{sample_parsed_document.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not cache_path.exists()


class TestListDocumentsEndpoint:
    """Tests for document listing endpoint."""

    def test_list_empty(self, client: TestClient):
        """Listing with no documents should return empty list."""
        response = client.get("/api/v1/parse")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_with_documents(
        self,
        client: TestClient,
        test_settings,
        sample_parsed_document: ParsedDocument,
    ):
        """Listing with documents should return summaries."""
        cache_path = test_settings.storage_path / f"{sample_parsed_document.id}.json"
        with open(cache_path, "w") as f:
            f.write(sample_parsed_document.model_dump_json())

        response = client.get("/api/v1/parse")

        assert response.status_code == status.HTTP_200_OK
        docs = response.json()
        assert len(docs) == 1
        assert docs[0]["id"] == sample_parsed_document.id
        assert docs[0]["filename"] == sample_parsed_document.filename
