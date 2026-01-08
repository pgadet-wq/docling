"""Tests for IOSA Document Parser
=================================

Tests the IOSA parsing pipeline, extractor, and chunking.
"""

import json
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling.iosa.config import IOSAConfig, TableMode, DeviceType
from docling.iosa.extractor import IOSAExtractor, IOSAStandard, find_all_standards
from docling.iosa.models import (
    IOSAStandardCode,
    ComplianceStatus,
    IOSADocument,
    IOSAParseResult,
)
from docling.iosa.chunking import IOSAChunker


# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "data"
MMEL_PDF = Path("/home/user/docling/data/mmel/PC_12_MMEL_02395_1_8_4edcc764b4.pdf")
MEL_PDF = Path("/home/user/docling/data/mel/MEL_PC-12_ISS01_REV00.pdf")


class TestIOSAConfig:
    """Tests for IOSA configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = IOSAConfig()
        assert config.device == DeviceType.CUDA
        assert config.table_mode == TableMode.HYBRID
        assert config.enable_ocr is True
        assert config.enable_chunking is True

    def test_cpu_config(self):
        """Test CPU configuration."""
        config = IOSAConfig(device=DeviceType.CPU)
        assert config.device == DeviceType.CPU

    def test_chunk_config(self):
        """Test chunking configuration."""
        config = IOSAConfig(chunk_size=256, chunk_overlap=32)
        assert config.chunk_size == 256
        assert config.chunk_overlap == 32


class TestIOSAExtractor:
    """Tests for IOSA standards extractor."""

    def test_extract_standard_codes(self):
        """Test extraction of standard codes from text."""
        text = """
        The operator shall comply with ORG 1.1.1 and FLT 2.3.4.
        Reference: DSP 3.1.2 provides guidance on operational control.
        See also MNT 4.5.6 for maintenance requirements.
        """
        standards = find_all_standards(text)
        assert "ORG 1.1.1" in standards
        assert "FLT 2.3.4" in standards
        assert "DSP 3.1.2" in standards
        assert "MNT 4.5.6" in standards

    def test_extract_with_target_filter(self):
        """Test extraction with target filter."""
        extractor = IOSAExtractor(target_standards=[IOSAStandard.ORG, IOSAStandard.FLT])
        text = "ORG 1.1.1 shall be met. DSP 2.2.2 is also required."
        items = extractor.extract_from_text(text)

        codes = [item.reference_number for item in items]
        assert "ORG 1.1.1" in codes
        # DSP should not be extracted due to filter
        assert "DSP 2.2.2" not in codes

    def test_extract_priority(self):
        """Test extraction of requirement priority."""
        extractor = IOSAExtractor()

        text_shall = "The operator shall comply with ORG 1.1.1"
        items = extractor.extract_from_text(text_shall)
        assert items[0].priority == "shall"

        text_should = "The operator should consider FLT 2.2.2"
        items = extractor.extract_from_text(text_should)
        assert items[0].priority == "should"

        text_may = "The operator may implement MNT 3.3.3"
        items = extractor.extract_from_text(text_may)
        assert items[0].priority == "may"

    def test_all_standard_codes(self):
        """Test all standard codes are recognized."""
        extractor = IOSAExtractor()
        text = """
        ORG 1.1 FLT 2.1 DSP 3.1 MNT 4.1
        CAB 5.1 GRH 6.1 CGO 7.1 SEC 8.1
        """
        items = extractor.extract_from_text(text)
        codes = {item.standard_code for item in items}

        assert IOSAStandardCode.ORG in codes
        assert IOSAStandardCode.FLT in codes
        assert IOSAStandardCode.DSP in codes
        assert IOSAStandardCode.MNT in codes
        assert IOSAStandardCode.CAB in codes
        assert IOSAStandardCode.GRH in codes
        assert IOSAStandardCode.CGO in codes
        assert IOSAStandardCode.SEC in codes


class TestIOSAChunker:
    """Tests for IOSA document chunker."""

    def test_chunker_initialization(self):
        """Test chunker initialization."""
        chunker = IOSAChunker(chunk_size=512, chunk_overlap=64)
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 64

    def test_chunk_size_limits(self):
        """Test that chunks respect size limits."""
        chunker = IOSAChunker(chunk_size=100)  # Small chunks for testing

        # Create a long text
        long_text = " ".join(["word"] * 500)
        buffer = [(long_text, 1, "text")]

        chunks = chunker._create_chunks_from_buffer(
            [(long_text, 0, None)],
            "doc1",
            "test.pdf",
            "Test Section",
            None,
        )

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should be reasonably sized
        for chunk in chunks:
            assert len(chunk.content) <= chunker._chunk_chars + 500  # Allow some overflow

    def test_chunk_metadata(self):
        """Test chunk metadata generation."""
        chunker = IOSAChunker()

        text = "This is a test paragraph about aviation safety."
        buffer = [(text, 5, None)]

        chunks = chunker._create_chunks_from_buffer(
            buffer,
            "doc123",
            "manual.pdf",
            "Safety Section",
            IOSAStandardCode.ORG,
        )

        assert len(chunks) == 1
        chunk = chunks[0]

        assert chunk.metadata.document_id == "doc123"
        assert chunk.metadata.source_file == "manual.pdf"
        assert chunk.metadata.section_title == "Safety Section"
        assert chunk.metadata.standard_code == IOSAStandardCode.ORG
        assert 5 in chunk.metadata.page_numbers


class TestIOSAParser:
    """Tests for IOSA parser (integration tests)."""

    @pytest.mark.skipif(
        not MMEL_PDF.exists(),
        reason="MMEL PDF not found"
    )
    def test_parse_mmel_document(self):
        """Test parsing MMEL document."""
        from docling.iosa.parser import IOSAParser

        config = IOSAConfig(
            device=DeviceType.CPU,  # Use CPU for testing
            table_mode=TableMode.STANDARD,
            enable_chunking=True,
            chunk_size=256,
        )

        parser = IOSAParser(config=config)
        result = parser.parse(MMEL_PDF)

        assert result.success
        assert result.document is not None
        assert result.document.metadata.document_type == "MMEL"
        assert result.document.metadata.total_pages > 0

    @pytest.mark.skipif(
        not MEL_PDF.exists(),
        reason="MEL PDF not found"
    )
    def test_parse_mel_document(self):
        """Test parsing MEL document."""
        from docling.iosa.parser import IOSAParser

        config = IOSAConfig(
            device=DeviceType.CPU,
            table_mode=TableMode.STANDARD,
        )

        parser = IOSAParser(config=config)
        result = parser.parse(MEL_PDF)

        assert result.success
        assert result.document is not None
        assert result.document.metadata.document_type == "MEL"


class TestIOSAModels:
    """Tests for IOSA data models."""

    def test_compliance_item_model(self):
        """Test ComplianceItem model."""
        from docling.iosa.models import ComplianceItem

        item = ComplianceItem(
            standard_code=IOSAStandardCode.ORG,
            reference_number="ORG 1.1.1",
            requirement_text="The operator shall have a safety management system.",
            priority="shall",
            page_references=[1, 2, 3],
        )

        assert item.standard_code == IOSAStandardCode.ORG
        assert item.reference_number == "ORG 1.1.1"
        assert item.priority == "shall"
        assert 1 in item.page_references

    def test_iosa_document_model(self):
        """Test IOSADocument model."""
        from docling.iosa.models import IOSADocument, DocumentMetadata

        metadata = DocumentMetadata(
            document_id="doc123",
            filename="test.pdf",
            document_type="IOSA Manual",
            total_pages=100,
        )

        doc = IOSADocument(metadata=metadata)
        assert doc.metadata.document_id == "doc123"
        assert doc.metadata.total_pages == 100


# CLI test
def test_cli_import():
    """Test that IOSA module can be imported."""
    from docling.iosa import (
        IOSAConfig,
        IOSAParser,
        IOSAExtractor,
        HybridIOSAPipeline,
    )

    assert IOSAConfig is not None
    assert IOSAParser is not None
    assert IOSAExtractor is not None
    assert HybridIOSAPipeline is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
