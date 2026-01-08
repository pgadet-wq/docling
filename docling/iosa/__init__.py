"""IOSA Document Parser Module
==============================

A specialized module for parsing IOSA (IATA Operational Safety Audit) aviation documents
using a hybrid approach:
- Standard Docling pipeline for text extraction (fast)
- VLM (Vision Language Model) pipeline for table extraction (precise, +26% accuracy)

Key components:
- HybridIOSAPipeline: Combines standard and VLM pipelines
- IOSAExtractor: Extracts IOSA standards (ORG, FLT, DSP, MNT, CAB, GRH, CGO, SEC)
- IOSAChunker: Creates chunks for LLM/RAG applications
- FastAPI service: REST API for document processing

Usage:
    from docling.iosa import IOSAParser, IOSAConfig

    parser = IOSAParser(config=IOSAConfig(
        vlm_model="pgadet-wq/granite-docling-258M",
        use_gpu=True
    ))
    result = parser.parse("manual.pdf")
"""

from docling.iosa.config import IOSAConfig
from docling.iosa.extractor import IOSAExtractor, IOSAStandard
from docling.iosa.models import (
    ChunkMetadata,
    ComplianceItem,
    IOSAChunk,
    IOSADocument,
    IOSAParseResult,
    IOSASection,
    TableExtractionResult,
)
from docling.iosa.parser import IOSAParser
from docling.iosa.pipeline import HybridIOSAPipeline

__all__ = [
    # Configuration
    "IOSAConfig",
    # Pipeline
    "HybridIOSAPipeline",
    # Parser
    "IOSAParser",
    # Extractor
    "IOSAExtractor",
    "IOSAStandard",
    # Models
    "IOSADocument",
    "IOSASection",
    "IOSAChunk",
    "ChunkMetadata",
    "ComplianceItem",
    "TableExtractionResult",
    "IOSAParseResult",
]
