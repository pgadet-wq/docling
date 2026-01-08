"""IOSA Data Models
==================

Pydantic models for IOSA document parsing results.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class IOSAStandardCode(str, Enum):
    """IOSA Standard Codes."""

    ORG = "ORG"  # Organization and Management System
    FLT = "FLT"  # Flight Operations
    DSP = "DSP"  # Operational Control and Flight Dispatch
    MNT = "MNT"  # Aircraft Engineering and Maintenance
    CAB = "CAB"  # Cabin Operations
    GRH = "GRH"  # Ground Handling
    CGO = "CGO"  # Cargo Operations
    SEC = "SEC"  # Security Management


class ComplianceStatus(str, Enum):
    """Compliance status for IOSA requirements."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    UNKNOWN = "unknown"


class ElementType(str, Enum):
    """Document element types."""

    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    HEADING = "heading"
    LIST = "list"
    CODE = "code"
    REFERENCE = "reference"


class BoundingBox(BaseModel):
    """Bounding box coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float
    page: int


class TableCell(BaseModel):
    """Table cell data."""

    text: str
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TableExtractionResult(BaseModel):
    """Result of table extraction."""

    table_id: str
    page_number: int
    rows: int
    cols: int
    cells: List[TableCell]
    html: str
    markdown: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = "standard"  # "standard" or "vlm"
    bbox: Optional[BoundingBox] = None
    caption: Optional[str] = None


class ComplianceItem(BaseModel):
    """IOSA compliance requirement item."""

    standard_code: IOSAStandardCode
    reference_number: str  # e.g., "ORG 1.1.1"
    requirement_text: str
    guidance_text: Optional[str] = None
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    evidence: Optional[str] = None
    notes: Optional[str] = None
    page_references: List[int] = Field(default_factory=list)
    related_items: List[str] = Field(default_factory=list)
    priority: Optional[str] = None  # "shall", "should", "may"


class IOSASection(BaseModel):
    """A section of an IOSA document."""

    section_id: str
    title: str
    level: int = 1  # Heading level
    content: str
    page_start: int
    page_end: int
    standard_code: Optional[IOSAStandardCode] = None
    subsections: List["IOSASection"] = Field(default_factory=list)
    tables: List[TableExtractionResult] = Field(default_factory=list)
    compliance_items: List[ComplianceItem] = Field(default_factory=list)


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    chunk_id: str
    document_id: str
    page_numbers: List[int]
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    standard_code: Optional[IOSAStandardCode] = None
    element_types: List[ElementType] = Field(default_factory=list)
    has_table: bool = False
    has_figure: bool = False
    token_count: int = 0
    char_count: int = 0
    source_file: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IOSAChunk(BaseModel):
    """A chunk of IOSA document for RAG/LLM."""

    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None  # Optional embedding vector


class DocumentMetadata(BaseModel):
    """Metadata for an IOSA document."""

    document_id: str
    filename: str
    title: Optional[str] = None
    document_type: Optional[str] = None  # "IATA Standards Manual", "MEL", "MMEL", etc.
    revision: Optional[str] = None
    effective_date: Optional[datetime] = None
    total_pages: int = 0
    file_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    standard_codes_found: List[IOSAStandardCode] = Field(default_factory=list)
    table_count: int = 0
    figure_count: int = 0


class IOSADocument(BaseModel):
    """Complete parsed IOSA document."""

    metadata: DocumentMetadata
    sections: List[IOSASection] = Field(default_factory=list)
    tables: List[TableExtractionResult] = Field(default_factory=list)
    compliance_items: List[ComplianceItem] = Field(default_factory=list)
    raw_text: str = ""
    markdown: str = ""
    html: str = ""


class IOSAParseResult(BaseModel):
    """Result of parsing an IOSA document."""

    success: bool
    document: Optional[IOSADocument] = None
    chunks: List[IOSAChunk] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_stats: Dict[str, Any] = Field(default_factory=dict)

    # Output files (if generated)
    json_output: Optional[str] = None
    markdown_output: Optional[str] = None
    html_output: Optional[str] = None
    chunks_output: Optional[str] = None


# Update forward references
IOSASection.model_rebuild()
