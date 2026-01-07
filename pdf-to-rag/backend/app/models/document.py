"""Pydantic models for parsed PDF documents.

This module defines the data structures used to represent parsed PDF content
with bounding boxes for spatial positioning and hierarchical relationships.
"""

from datetime import datetime
from typing import Any, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Bounding box with normalized coordinates [0-1].

    Coordinates are normalized relative to page dimensions,
    allowing consistent positioning across different PDF sizes.

    Attributes:
        x0: Left coordinate (0 = left edge, 1 = right edge)
        y0: Top coordinate (0 = top edge, 1 = bottom edge)
        x1: Right coordinate (must be >= x0)
        y1: Bottom coordinate (must be >= y0)
        page: Page number (1-indexed)
    """

    x0: float = Field(..., ge=0.0, le=1.0, description="Left coordinate normalized [0-1]")
    y0: float = Field(..., ge=0.0, le=1.0, description="Top coordinate normalized [0-1]")
    x1: float = Field(..., ge=0.0, le=1.0, description="Right coordinate normalized [0-1]")
    y1: float = Field(..., ge=0.0, le=1.0, description="Bottom coordinate normalized [0-1]")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")

    @field_validator("x1")
    @classmethod
    def x1_must_be_greater_than_x0(cls, v: float, info) -> float:
        """Validate that x1 >= x0."""
        if "x0" in info.data and v < info.data["x0"]:
            raise ValueError("x1 must be greater than or equal to x0")
        return v

    @field_validator("y1")
    @classmethod
    def y1_must_be_greater_than_y0(cls, v: float, info) -> float:
        """Validate that y1 >= y0."""
        if "y0" in info.data and v < info.data["y0"]:
            raise ValueError("y1 must be greater than or equal to y0")
        return v

    @property
    def width(self) -> float:
        """Calculate normalized width of bounding box."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Calculate normalized height of bounding box."""
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        """Calculate normalized area of bounding box."""
        return self.width * self.height


# Block type literals for type safety
BlockType = Literal[
    "title",
    "paragraph",
    "table",
    "list",
    "list_item",
    "image",
    "header",
    "footer",
    "caption",
    "code",
    "equation",
    "unknown",
]


class DocumentBlock(BaseModel):
    """A content block extracted from a PDF document.

    Represents a single semantic unit of content (paragraph, title, etc.)
    with its spatial position and hierarchical relationships.

    Attributes:
        id: Unique identifier for this block
        type: Semantic type of the block
        text: Extracted text content
        bbox: Bounding box with normalized coordinates
        level: Heading level (1-6) for title blocks
        parent_id: ID of parent block in hierarchy
        children_ids: IDs of child blocks
        confidence: OCR confidence score [0-1]
        metadata: Additional block-specific metadata
        hidden: Soft delete flag for UI filtering
        keep_with_next: Hint for chunking - keep with next block
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique block identifier")
    type: BlockType = Field(..., description="Semantic type of the block")
    text: str = Field(..., description="Extracted text content")
    bbox: BoundingBox = Field(..., description="Bounding box with normalized coordinates")
    level: Optional[int] = Field(
        default=None, ge=1, le=6, description="Heading level for titles (1-6)"
    )
    parent_id: Optional[str] = Field(default=None, description="Parent block ID in hierarchy")
    children_ids: list[str] = Field(default_factory=list, description="Child block IDs")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="OCR confidence score [0-1]"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional block metadata"
    )
    hidden: bool = Field(default=False, description="Soft delete flag")
    keep_with_next: bool = Field(default=False, description="Chunking hint - keep with next block")

    model_config = {"frozen": False, "extra": "forbid"}


class TableCell(BaseModel):
    """A cell within a table structure.

    Attributes:
        row: Row index (0-indexed)
        col: Column index (0-indexed)
        row_span: Number of rows this cell spans
        col_span: Number of columns this cell spans
        text: Cell text content
        is_header: Whether this cell is a header cell
        bbox: Optional bounding box for the cell
    """

    row: int = Field(..., ge=0, description="Row index (0-indexed)")
    col: int = Field(..., ge=0, description="Column index (0-indexed)")
    row_span: int = Field(default=1, ge=1, description="Number of rows spanned")
    col_span: int = Field(default=1, ge=1, description="Number of columns spanned")
    text: str = Field(..., description="Cell text content")
    is_header: bool = Field(default=False, description="Whether this is a header cell")
    bbox: Optional[BoundingBox] = Field(default=None, description="Cell bounding box")


class TableBlock(DocumentBlock):
    """A table block with structured cell data.

    Extends DocumentBlock with table-specific attributes including
    row/column structure and individual cell data.

    Attributes:
        rows: Total number of rows
        cols: Total number of columns
        cells: List of table cells with their content and positions
    """

    type: Literal["table"] = Field(default="table", description="Block type (always 'table')")
    rows: int = Field(..., ge=1, description="Total number of rows")
    cols: int = Field(..., ge=1, description="Total number of columns")
    cells: list[TableCell] = Field(..., description="Table cell data")

    @field_validator("cells")
    @classmethod
    def validate_cells(cls, v: list[TableCell], info) -> list[TableCell]:
        """Validate that cells don't exceed table dimensions."""
        if "rows" in info.data and "cols" in info.data:
            max_row = info.data["rows"]
            max_col = info.data["cols"]
            for cell in v:
                if cell.row >= max_row:
                    raise ValueError(f"Cell row {cell.row} exceeds table rows {max_row}")
                if cell.col >= max_col:
                    raise ValueError(f"Cell col {cell.col} exceeds table cols {max_col}")
        return v


class PageInfo(BaseModel):
    """Information about a single page in the document.

    Attributes:
        page_number: Page number (1-indexed)
        width: Original page width in points
        height: Original page height in points
        block_count: Number of blocks on this page
    """

    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    width: float = Field(..., gt=0, description="Page width in points")
    height: float = Field(..., gt=0, description="Page height in points")
    block_count: int = Field(default=0, ge=0, description="Number of blocks on this page")


class ParsedDocument(BaseModel):
    """A fully parsed PDF document with all extracted content.

    Represents the complete parsing result including all blocks,
    metadata, and page information.

    Attributes:
        id: Unique document identifier
        filename: Original PDF filename
        total_pages: Total number of pages
        blocks: All extracted content blocks
        pages: Information about each page
        metadata: Document-level metadata
        created_at: Timestamp of parsing
        processing_time_ms: Time taken to parse (milliseconds)
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique document ID")
    filename: str = Field(..., description="Original PDF filename")
    total_pages: int = Field(..., ge=1, description="Total number of pages")
    blocks: list[Union[DocumentBlock, TableBlock]] = Field(
        ..., description="All extracted content blocks"
    )
    pages: list[PageInfo] = Field(default_factory=list, description="Page information")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document-level metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Parsing timestamp"
    )
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")

    def get_blocks_by_page(self, page_number: int) -> list[Union[DocumentBlock, TableBlock]]:
        """Get all blocks for a specific page.

        Args:
            page_number: The page number (1-indexed)

        Returns:
            List of blocks on the specified page
        """
        return [block for block in self.blocks if block.bbox.page == page_number]

    def get_blocks_by_type(
        self, block_type: BlockType
    ) -> list[Union[DocumentBlock, TableBlock]]:
        """Get all blocks of a specific type.

        Args:
            block_type: The type of blocks to retrieve

        Returns:
            List of blocks matching the specified type
        """
        return [block for block in self.blocks if block.type == block_type]

    @property
    def table_count(self) -> int:
        """Count of table blocks in the document."""
        return len([b for b in self.blocks if b.type == "table"])

    @property
    def visible_blocks(self) -> list[Union[DocumentBlock, TableBlock]]:
        """Get all non-hidden blocks."""
        return [b for b in self.blocks if not b.hidden]


class ParseRequest(BaseModel):
    """Request model for document parsing configuration.

    Attributes:
        extract_tables: Whether to extract table structure
        extract_images: Whether to extract image metadata
        ocr_enabled: Whether to run OCR on images
        language: Primary document language for OCR
    """

    extract_tables: bool = Field(default=True, description="Extract table structure")
    extract_images: bool = Field(default=True, description="Extract image metadata")
    ocr_enabled: bool = Field(default=True, description="Enable OCR for images")
    language: str = Field(default="en", description="Primary document language")


class ParseResponse(BaseModel):
    """Response wrapper for parsed document.

    Attributes:
        success: Whether parsing was successful
        document: The parsed document (if successful)
        error: Error message (if failed)
    """

    success: bool = Field(..., description="Whether parsing succeeded")
    document: Optional[ParsedDocument] = Field(
        default=None, description="Parsed document"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
