"""Docling service for PDF parsing and content extraction.

This module provides the core PDF parsing functionality using IBM Docling,
converting PDF documents into structured content with bounding boxes.
"""

import time
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from app.config import Settings, get_settings
from app.models.document import (
    BoundingBox,
    DocumentBlock,
    PageInfo,
    ParsedDocument,
    TableBlock,
    TableCell,
)

# Docling imports
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    OcrMacOptions,
    PdfPipelineOptions,
    TableFormerMode,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument, NodeItem, TableItem


class DoclingService:
    """Service for parsing PDF documents using IBM Docling.

    This service initializes Docling with appropriate GPU/CPU configuration
    and provides methods to parse PDFs into structured content with
    normalized bounding boxes.

    Attributes:
        settings: Application settings
        converter: Docling DocumentConverter instance
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the Docling service.

        Args:
            settings: Application settings (uses defaults if not provided)
        """
        self.settings = settings or get_settings()
        self._converter: Optional[DocumentConverter] = None
        self._initialized = False

    @property
    def converter(self) -> DocumentConverter:
        """Get or initialize the DocumentConverter.

        Lazy initialization to avoid loading models at import time.

        Returns:
            Configured DocumentConverter instance
        """
        if self._converter is None:
            self._initialize_converter()
        return self._converter

    def _initialize_converter(self) -> None:
        """Initialize Docling DocumentConverter with appropriate settings."""
        logger.info(
            "Initializing Docling converter",
            use_gpu=self.settings.use_gpu,
            device=self.settings.device,
        )

        start_time = time.time()

        # Configure OCR options based on availability
        ocr_options = self._get_ocr_options()

        # Configure pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.settings.docling_ocr_enabled
        pipeline_options.do_table_structure = self.settings.docling_table_extraction

        if self.settings.docling_table_extraction:
            # Use accurate mode for better table extraction
            pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

        if ocr_options:
            pipeline_options.ocr_options = ocr_options

        # Create converter with PDF format option
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        init_time = time.time() - start_time
        logger.info(f"Docling converter initialized in {init_time:.2f}s")
        self._initialized = True

    def _get_ocr_options(self) -> Optional[Any]:
        """Get appropriate OCR options based on available backends.

        Returns:
            OCR options object or None if OCR is disabled
        """
        if not self.settings.docling_ocr_enabled:
            return None

        # Try EasyOCR first (good GPU support)
        try:
            return EasyOcrOptions(use_gpu=self.settings.use_gpu)
        except Exception:
            logger.debug("EasyOCR not available, trying Tesseract")

        # Fall back to Tesseract
        try:
            return TesseractOcrOptions()
        except Exception:
            try:
                return TesseractCliOcrOptions()
            except Exception:
                logger.warning("No OCR backend available, OCR disabled")
                return None

    def parse_pdf(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
    ) -> ParsedDocument:
        """Parse a PDF document and extract structured content.

        Args:
            file_bytes: Raw PDF file bytes
            filename: Original filename for metadata

        Returns:
            ParsedDocument with all extracted blocks and metadata

        Raises:
            ValueError: If the PDF is invalid or cannot be parsed
            TimeoutError: If processing exceeds timeout
        """
        start_time = time.time()
        doc_id = str(uuid4())

        logger.info(
            "Starting PDF parsing",
            doc_id=doc_id,
            filename=filename,
            size_bytes=len(file_bytes),
        )

        try:
            # Convert PDF using Docling
            source = BytesIO(file_bytes)
            result = self.converter.convert(source, raises_on_error=True)
            docling_doc = result.document

            # Extract page information
            pages = self._extract_page_info(docling_doc)
            total_pages = len(pages) if pages else 1

            # Convert Docling document to our block format
            blocks = self._convert_to_blocks(docling_doc, pages)

            # Build parent-child relationships
            self._build_hierarchy(blocks)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Create parsed document
            parsed_doc = ParsedDocument(
                id=doc_id,
                filename=filename,
                total_pages=total_pages,
                blocks=blocks,
                pages=pages,
                metadata=self._extract_metadata(docling_doc),
                processing_time_ms=processing_time_ms,
            )

            logger.info(
                "PDF parsing completed",
                doc_id=doc_id,
                total_pages=total_pages,
                block_count=len(blocks),
                processing_time_ms=processing_time_ms,
            )

            return parsed_doc

        except Exception as e:
            logger.error(
                "PDF parsing failed",
                doc_id=doc_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ValueError(f"Failed to parse PDF: {str(e)}") from e

    def _extract_page_info(self, doc: DoclingDocument) -> list[PageInfo]:
        """Extract page information from Docling document.

        Args:
            doc: Docling document

        Returns:
            List of PageInfo objects
        """
        pages = []

        if hasattr(doc, "pages") and doc.pages:
            for page_no, page in doc.pages.items():
                page_num = int(page_no) if isinstance(page_no, str) else page_no
                width = getattr(page, "width", 612.0)  # Default letter size
                height = getattr(page, "height", 792.0)
                pages.append(
                    PageInfo(
                        page_number=page_num,
                        width=float(width),
                        height=float(height),
                        block_count=0,  # Will be updated later
                    )
                )

        # Sort by page number
        pages.sort(key=lambda p: p.page_number)

        # If no pages found, create a default
        if not pages:
            pages.append(
                PageInfo(page_number=1, width=612.0, height=792.0, block_count=0)
            )

        return pages

    def _convert_to_blocks(
        self,
        doc: DoclingDocument,
        pages: list[PageInfo],
    ) -> list[DocumentBlock | TableBlock]:
        """Convert Docling document to our block format.

        Args:
            doc: Docling document
            pages: Page information for normalization

        Returns:
            List of DocumentBlock and TableBlock objects
        """
        blocks: list[DocumentBlock | TableBlock] = []
        page_dimensions = {p.page_number: (p.width, p.height) for p in pages}

        # Process document body items
        if hasattr(doc, "body") and doc.body:
            self._process_body(doc, doc.body, blocks, page_dimensions)

        # Process tables separately if available
        if hasattr(doc, "tables") and doc.tables:
            for table_item in doc.tables:
                table_block = self._convert_table(table_item, page_dimensions)
                if table_block:
                    blocks.append(table_block)

        # Update page block counts
        for page in pages:
            page.block_count = len([b for b in blocks if b.bbox.page == page.page_number])

        return blocks

    def _process_body(
        self,
        doc: DoclingDocument,
        body: Any,
        blocks: list[DocumentBlock | TableBlock],
        page_dimensions: dict[int, tuple[float, float]],
    ) -> None:
        """Process document body recursively.

        Args:
            doc: Parent Docling document
            body: Body element to process
            blocks: List to append blocks to
            page_dimensions: Page dimension lookup
        """
        # Handle different body structures
        items = []
        if hasattr(body, "children"):
            items = body.children
        elif hasattr(body, "__iter__"):
            items = list(body)
        elif hasattr(body, "items"):
            items = list(body.items()) if callable(body.items) else body.items

        for item in items:
            block = self._convert_node_to_block(item, page_dimensions)
            if block:
                blocks.append(block)

            # Recursively process children
            if hasattr(item, "children") and item.children:
                self._process_body(doc, item.children, blocks, page_dimensions)

    def _convert_node_to_block(
        self,
        node: Any,
        page_dimensions: dict[int, tuple[float, float]],
    ) -> Optional[DocumentBlock]:
        """Convert a Docling node to a DocumentBlock.

        Args:
            node: Docling node item
            page_dimensions: Page dimension lookup

        Returns:
            DocumentBlock or None if conversion fails
        """
        try:
            # Get text content
            text = ""
            if hasattr(node, "text"):
                text = str(node.text) if node.text else ""
            elif hasattr(node, "export_to_text"):
                text = node.export_to_text()

            if not text.strip():
                return None

            # Get bounding box
            bbox = self._extract_bbox(node, page_dimensions)
            if not bbox:
                return None

            # Determine block type
            block_type = self._get_block_type(node)

            # Get heading level if applicable
            level = None
            if block_type == "title" and hasattr(node, "level"):
                level = node.level

            # Create block
            return DocumentBlock(
                id=str(uuid4()),
                type=block_type,
                text=text,
                bbox=bbox,
                level=level,
                confidence=self._get_confidence(node),
                metadata=self._get_node_metadata(node),
            )

        except Exception as e:
            logger.debug(f"Failed to convert node: {e}")
            return None

    def _extract_bbox(
        self,
        node: Any,
        page_dimensions: dict[int, tuple[float, float]],
    ) -> Optional[BoundingBox]:
        """Extract normalized bounding box from a node.

        Args:
            node: Node with bounding box information
            page_dimensions: Page dimensions for normalization

        Returns:
            Normalized BoundingBox or None
        """
        try:
            # Try different bbox attribute names
            prov = None
            if hasattr(node, "prov") and node.prov:
                prov = node.prov[0] if isinstance(node.prov, list) else node.prov
            elif hasattr(node, "provenance") and node.provenance:
                prov = node.provenance[0] if isinstance(node.provenance, list) else node.provenance

            if not prov:
                return None

            # Get page number
            page = 1
            if hasattr(prov, "page_no"):
                page = int(prov.page_no)
            elif hasattr(prov, "page"):
                page = int(prov.page)

            # Get bounding box coordinates
            bbox_data = None
            if hasattr(prov, "bbox"):
                bbox_data = prov.bbox
            elif hasattr(prov, "bounding_box"):
                bbox_data = prov.bounding_box

            if not bbox_data:
                return None

            # Extract coordinates
            if hasattr(bbox_data, "l"):
                x0, y0, x1, y1 = bbox_data.l, bbox_data.t, bbox_data.r, bbox_data.b
            elif hasattr(bbox_data, "x0"):
                x0, y0, x1, y1 = bbox_data.x0, bbox_data.y0, bbox_data.x1, bbox_data.y1
            elif isinstance(bbox_data, (list, tuple)) and len(bbox_data) >= 4:
                x0, y0, x1, y1 = bbox_data[:4]
            else:
                return None

            # Normalize coordinates
            width, height = page_dimensions.get(page, (612.0, 792.0))

            # Normalize to [0, 1] range
            x0_norm = max(0.0, min(1.0, float(x0) / width))
            y0_norm = max(0.0, min(1.0, float(y0) / height))
            x1_norm = max(0.0, min(1.0, float(x1) / width))
            y1_norm = max(0.0, min(1.0, float(y1) / height))

            # Ensure x1 > x0 and y1 > y0
            if x1_norm <= x0_norm:
                x1_norm = min(1.0, x0_norm + 0.01)
            if y1_norm <= y0_norm:
                y1_norm = min(1.0, y0_norm + 0.01)

            return BoundingBox(
                x0=x0_norm,
                y0=y0_norm,
                x1=x1_norm,
                y1=y1_norm,
                page=page,
            )

        except Exception as e:
            logger.debug(f"Failed to extract bbox: {e}")
            return None

    def _get_block_type(self, node: Any) -> str:
        """Determine block type from Docling node.

        Args:
            node: Docling node

        Returns:
            Block type string
        """
        # Check node type attribute
        if hasattr(node, "label"):
            label = str(node.label).lower()
            type_mapping = {
                "title": "title",
                "section_header": "title",
                "heading": "title",
                "paragraph": "paragraph",
                "text": "paragraph",
                "table": "table",
                "list": "list",
                "list_item": "list_item",
                "picture": "image",
                "image": "image",
                "figure": "image",
                "caption": "caption",
                "header": "header",
                "footer": "footer",
                "code": "code",
                "equation": "equation",
                "formula": "equation",
            }
            return type_mapping.get(label, "paragraph")

        # Check class name
        class_name = type(node).__name__.lower()
        if "heading" in class_name or "title" in class_name:
            return "title"
        elif "table" in class_name:
            return "table"
        elif "list" in class_name:
            return "list"
        elif "image" in class_name or "picture" in class_name:
            return "image"
        elif "caption" in class_name:
            return "caption"

        return "paragraph"

    def _get_confidence(self, node: Any) -> float:
        """Extract confidence score from node.

        Args:
            node: Docling node

        Returns:
            Confidence score [0-1]
        """
        if hasattr(node, "confidence"):
            return float(node.confidence)
        if hasattr(node, "score"):
            return float(node.score)
        return 1.0

    def _get_node_metadata(self, node: Any) -> dict[str, Any]:
        """Extract additional metadata from node.

        Args:
            node: Docling node

        Returns:
            Metadata dictionary
        """
        metadata = {}

        if hasattr(node, "name"):
            metadata["name"] = str(node.name)
        if hasattr(node, "label"):
            metadata["original_label"] = str(node.label)
        if hasattr(node, "ref"):
            metadata["ref"] = str(node.ref)

        return metadata

    def _convert_table(
        self,
        table: Any,
        page_dimensions: dict[int, tuple[float, float]],
    ) -> Optional[TableBlock]:
        """Convert a Docling table to TableBlock.

        Args:
            table: Docling table item
            page_dimensions: Page dimensions for normalization

        Returns:
            TableBlock or None
        """
        try:
            # Get table bounding box
            bbox = self._extract_bbox(table, page_dimensions)
            if not bbox:
                # Create default bbox if not available
                bbox = BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=0.1, page=1)

            # Extract table structure
            cells = []
            rows = 0
            cols = 0

            if hasattr(table, "data") and hasattr(table.data, "table_cells"):
                for cell in table.data.table_cells:
                    row = getattr(cell, "row", 0)
                    col = getattr(cell, "col", 0)
                    row_span = getattr(cell, "row_span", 1)
                    col_span = getattr(cell, "col_span", 1)
                    text = getattr(cell, "text", "")
                    is_header = getattr(cell, "is_header", False)

                    rows = max(rows, row + row_span)
                    cols = max(cols, col + col_span)

                    cells.append(
                        TableCell(
                            row=row,
                            col=col,
                            row_span=row_span,
                            col_span=col_span,
                            text=str(text),
                            is_header=is_header,
                        )
                    )
            elif hasattr(table, "export_to_dataframe"):
                # Fall back to DataFrame export
                df = table.export_to_dataframe()
                rows = len(df)
                cols = len(df.columns)

                # Add header cells
                for col_idx, col_name in enumerate(df.columns):
                    cells.append(
                        TableCell(
                            row=0,
                            col=col_idx,
                            text=str(col_name),
                            is_header=True,
                        )
                    )

                # Add data cells
                for row_idx, row_data in df.iterrows():
                    for col_idx, value in enumerate(row_data):
                        cells.append(
                            TableCell(
                                row=int(row_idx) + 1,
                                col=col_idx,
                                text=str(value),
                                is_header=False,
                            )
                        )
                rows += 1  # Account for header row

            if not cells:
                return None

            # Get table text for search
            table_text = " | ".join(c.text for c in cells if c.text.strip())

            return TableBlock(
                id=str(uuid4()),
                type="table",
                text=table_text,
                bbox=bbox,
                rows=max(rows, 1),
                cols=max(cols, 1),
                cells=cells,
                confidence=self._get_confidence(table),
                metadata={"table_id": getattr(table, "id", None)},
            )

        except Exception as e:
            logger.debug(f"Failed to convert table: {e}")
            return None

    def _build_hierarchy(self, blocks: list[DocumentBlock | TableBlock]) -> None:
        """Build parent-child relationships between blocks.

        Uses heading levels to establish hierarchy.

        Args:
            blocks: List of blocks to update in-place
        """
        # Sort blocks by page and position
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox.page, b.bbox.y0, b.bbox.x0))

        # Track heading stack for hierarchy
        heading_stack: list[DocumentBlock] = []

        for block in sorted_blocks:
            if block.type == "title" and block.level:
                # Pop headings of same or lower level
                while heading_stack and (
                    heading_stack[-1].level is None
                    or heading_stack[-1].level >= block.level
                ):
                    heading_stack.pop()

                # Set parent if there's a higher-level heading
                if heading_stack:
                    block.parent_id = heading_stack[-1].id
                    heading_stack[-1].children_ids.append(block.id)

                # Push this heading onto stack
                heading_stack.append(block)

            elif heading_stack:
                # Non-heading blocks are children of the current heading
                block.parent_id = heading_stack[-1].id
                heading_stack[-1].children_ids.append(block.id)

    def _extract_metadata(self, doc: DoclingDocument) -> dict[str, Any]:
        """Extract document-level metadata.

        Args:
            doc: Docling document

        Returns:
            Metadata dictionary
        """
        metadata = {}

        # Try to extract various metadata fields
        if hasattr(doc, "name"):
            metadata["name"] = str(doc.name)
        if hasattr(doc, "origin"):
            origin = doc.origin
            if hasattr(origin, "filename"):
                metadata["original_filename"] = str(origin.filename)
            if hasattr(origin, "mimetype"):
                metadata["mimetype"] = str(origin.mimetype)

        if hasattr(doc, "metadata") and doc.metadata:
            doc_meta = doc.metadata
            if hasattr(doc_meta, "title"):
                metadata["title"] = str(doc_meta.title)
            if hasattr(doc_meta, "author"):
                metadata["author"] = str(doc_meta.author)
            if hasattr(doc_meta, "created"):
                metadata["created"] = str(doc_meta.created)

        return metadata


# Singleton instance for dependency injection
_docling_service: Optional[DoclingService] = None


def get_docling_service() -> DoclingService:
    """Get or create the Docling service singleton.

    Returns:
        DoclingService instance
    """
    global _docling_service
    if _docling_service is None:
        _docling_service = DoclingService()
    return _docling_service
