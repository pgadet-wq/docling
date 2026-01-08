"""IOSA Document Chunking
========================

Chunking utilities for preparing IOSA documents for LLM/RAG applications.

Features:
- Semantic chunking based on document structure
- Table-aware chunking (keeps tables intact)
- Metadata enrichment for retrieval
- Overlap handling for context preservation
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

from docling_core.types.doc import DoclingDocument, TableItem, TextItem

from docling.iosa.config import IOSAConfig
from docling.iosa.models import (
    ChunkMetadata,
    ElementType,
    IOSAChunk,
    IOSADocument,
    IOSAStandardCode,
)

_log = logging.getLogger(__name__)


class IOSAChunker:
    """Chunks IOSA documents for RAG/LLM applications.

    This chunker is optimized for aviation compliance documents:
    - Preserves table integrity
    - Maintains section context
    - Tracks standard code associations
    - Provides rich metadata for retrieval
    """

    # Default tokenizer estimation (chars per token)
    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 100,
        preserve_tables: bool = True,
        include_section_context: bool = True,
    ):
        """Initialize the chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            min_chunk_size: Minimum chunk size in tokens
            preserve_tables: Keep tables as single chunks
            include_section_context: Include section headers in chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.preserve_tables = preserve_tables
        self.include_section_context = include_section_context

        # Convert token sizes to character estimates
        self._chunk_chars = chunk_size * self.CHARS_PER_TOKEN
        self._overlap_chars = chunk_overlap * self.CHARS_PER_TOKEN
        self._min_chars = min_chunk_size * self.CHARS_PER_TOKEN

    def chunk_document(
        self,
        document: DoclingDocument,
        document_id: str,
        source_file: str = "",
    ) -> List[IOSAChunk]:
        """Chunk a DoclingDocument into RAG-ready chunks.

        Args:
            document: Parsed DoclingDocument
            document_id: Unique document identifier
            source_file: Source filename

        Returns:
            List of IOSAChunk objects
        """
        chunks: List[IOSAChunk] = []
        current_section = ""
        current_section_std: Optional[IOSAStandardCode] = None
        current_buffer: List[Tuple[str, int, ElementType]] = []

        # Iterate through document
        for item, level in document.iterate_items():
            page_no = self._get_page_number(item)

            if isinstance(item, TableItem):
                # Flush current buffer before table
                if current_buffer:
                    chunks.extend(
                        self._create_chunks_from_buffer(
                            current_buffer,
                            document_id,
                            source_file,
                            current_section,
                            current_section_std,
                        )
                    )
                    current_buffer = []

                # Create table chunk
                table_chunk = self._create_table_chunk(
                    item,
                    page_no,
                    document_id,
                    source_file,
                    current_section,
                    current_section_std,
                )
                if table_chunk:
                    chunks.append(table_chunk)

            elif isinstance(item, TextItem):
                text = item.text if hasattr(item, "text") else str(item)

                # Check if this is a section header
                if self._is_section_header(item, level):
                    # Flush buffer
                    if current_buffer:
                        chunks.extend(
                            self._create_chunks_from_buffer(
                                current_buffer,
                                document_id,
                                source_file,
                                current_section,
                                current_section_std,
                            )
                        )
                        current_buffer = []

                    current_section = text[:200]
                    current_section_std = self._extract_standard_code(text)

                # Add to buffer
                elem_type = self._determine_element_type(item, level)
                current_buffer.append((text, page_no, elem_type))

        # Flush remaining buffer
        if current_buffer:
            chunks.extend(
                self._create_chunks_from_buffer(
                    current_buffer,
                    document_id,
                    source_file,
                    current_section,
                    current_section_std,
                )
            )

        _log.info(f"Created {len(chunks)} chunks from document")
        return chunks

    def chunk_iosa_document(self, iosa_doc: IOSADocument) -> List[IOSAChunk]:
        """Chunk an IOSADocument.

        Args:
            iosa_doc: Parsed IOSADocument

        Returns:
            List of IOSAChunk objects
        """
        chunks: List[IOSAChunk] = []
        document_id = iosa_doc.metadata.document_id
        source_file = iosa_doc.metadata.filename

        # Chunk by sections
        for section in iosa_doc.sections:
            section_chunks = self._chunk_section(
                section, document_id, source_file
            )
            chunks.extend(section_chunks)

        # Add standalone table chunks
        for table in iosa_doc.tables:
            if not self._table_in_section(table, iosa_doc.sections):
                table_chunk = self._create_table_chunk_from_result(
                    table, document_id, source_file
                )
                if table_chunk:
                    chunks.append(table_chunk)

        return chunks

    def _create_chunks_from_buffer(
        self,
        buffer: List[Tuple[str, int, ElementType]],
        document_id: str,
        source_file: str,
        section_title: str,
        standard_code: Optional[IOSAStandardCode],
    ) -> List[IOSAChunk]:
        """Create chunks from accumulated buffer.

        Args:
            buffer: List of (text, page_no, element_type) tuples
            document_id: Document identifier
            source_file: Source filename
            section_title: Current section title
            standard_code: Current standard code

        Returns:
            List of chunks
        """
        if not buffer:
            return []

        chunks = []
        current_text = ""
        current_pages: List[int] = []
        current_types: List[ElementType] = []

        for text, page_no, elem_type in buffer:
            # Check if adding this text would exceed chunk size
            if len(current_text) + len(text) > self._chunk_chars and current_text:
                # Create chunk
                chunk = self._create_chunk(
                    current_text,
                    current_pages,
                    current_types,
                    document_id,
                    source_file,
                    section_title,
                    standard_code,
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_text)
                current_text = overlap_text + " " + text if overlap_text else text
                current_pages = [page_no]
                current_types = [elem_type]
            else:
                current_text += (" " if current_text else "") + text
                if page_no not in current_pages:
                    current_pages.append(page_no)
                if elem_type not in current_types:
                    current_types.append(elem_type)

        # Create final chunk
        if current_text and len(current_text) >= self._min_chars:
            chunk = self._create_chunk(
                current_text,
                current_pages,
                current_types,
                document_id,
                source_file,
                section_title,
                standard_code,
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(
        self,
        content: str,
        pages: List[int],
        element_types: List[ElementType],
        document_id: str,
        source_file: str,
        section_title: str,
        standard_code: Optional[IOSAStandardCode],
    ) -> IOSAChunk:
        """Create a single chunk with metadata.

        Args:
            content: Chunk content
            pages: Page numbers
            element_types: Element types in chunk
            document_id: Document identifier
            source_file: Source filename
            section_title: Section title
            standard_code: Standard code

        Returns:
            IOSAChunk object
        """
        chunk_id = self._generate_chunk_id(content, document_id)

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            page_numbers=pages,
            section_title=section_title if section_title else None,
            standard_code=standard_code,
            element_types=element_types,
            has_table=ElementType.TABLE in element_types,
            has_figure=ElementType.FIGURE in element_types,
            token_count=len(content) // self.CHARS_PER_TOKEN,
            char_count=len(content),
            source_file=source_file,
            created_at=datetime.utcnow(),
        )

        # Prepend section context if enabled
        if self.include_section_context and section_title:
            content = f"[Section: {section_title}]\n\n{content}"

        return IOSAChunk(content=content, metadata=metadata)

    def _create_table_chunk(
        self,
        table: TableItem,
        page_no: int,
        document_id: str,
        source_file: str,
        section_title: str,
        standard_code: Optional[IOSAStandardCode],
    ) -> Optional[IOSAChunk]:
        """Create a chunk from a table item.

        Args:
            table: TableItem
            page_no: Page number
            document_id: Document identifier
            source_file: Source filename
            section_title: Section title
            standard_code: Standard code

        Returns:
            IOSAChunk or None
        """
        # Extract table as markdown
        try:
            table_md = table.export_to_markdown()
        except Exception:
            table_md = str(table)

        if not table_md or len(table_md) < 10:
            return None

        # Add caption if available
        caption = ""
        if hasattr(table, "caption") and table.caption:
            caption = f"**Table: {table.caption}**\n\n"

        content = caption + table_md

        chunk_id = self._generate_chunk_id(content, document_id)

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            page_numbers=[page_no],
            section_title=section_title if section_title else None,
            standard_code=standard_code,
            element_types=[ElementType.TABLE],
            has_table=True,
            has_figure=False,
            token_count=len(content) // self.CHARS_PER_TOKEN,
            char_count=len(content),
            source_file=source_file,
            created_at=datetime.utcnow(),
        )

        return IOSAChunk(content=content, metadata=metadata)

    def _create_table_chunk_from_result(
        self,
        table: Any,
        document_id: str,
        source_file: str,
    ) -> Optional[IOSAChunk]:
        """Create chunk from TableExtractionResult.

        Args:
            table: TableExtractionResult
            document_id: Document identifier
            source_file: Source filename

        Returns:
            IOSAChunk or None
        """
        content = f"**Table**\n\n{table.markdown}"

        if table.caption:
            content = f"**Table: {table.caption}**\n\n{table.markdown}"

        if len(content) < 10:
            return None

        chunk_id = self._generate_chunk_id(content, document_id)

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            page_numbers=[table.page_number],
            standard_code=None,
            element_types=[ElementType.TABLE],
            has_table=True,
            has_figure=False,
            token_count=len(content) // self.CHARS_PER_TOKEN,
            char_count=len(content),
            source_file=source_file,
            created_at=datetime.utcnow(),
        )

        return IOSAChunk(content=content, metadata=metadata)

    def _chunk_section(
        self,
        section: Any,
        document_id: str,
        source_file: str,
    ) -> List[IOSAChunk]:
        """Chunk a section of an IOSA document.

        Args:
            section: IOSASection
            document_id: Document identifier
            source_file: Source filename

        Returns:
            List of chunks
        """
        chunks = []

        # Chunk section content
        if section.content:
            buffer = [(section.content, section.page_start, ElementType.TEXT)]
            chunks.extend(
                self._create_chunks_from_buffer(
                    buffer,
                    document_id,
                    source_file,
                    section.title,
                    section.standard_code,
                )
            )

        # Chunk section tables
        for table in section.tables:
            table_chunk = self._create_table_chunk_from_result(
                table, document_id, source_file
            )
            if table_chunk:
                table_chunk.metadata.section_title = section.title
                table_chunk.metadata.standard_code = section.standard_code
                chunks.append(table_chunk)

        # Recursively chunk subsections
        for subsection in section.subsections:
            chunks.extend(
                self._chunk_section(subsection, document_id, source_file)
            )

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from end of previous chunk.

        Args:
            text: Previous chunk text

        Returns:
            Overlap text
        """
        if len(text) <= self._overlap_chars:
            return text

        # Try to break at sentence boundary
        overlap_text = text[-self._overlap_chars:]
        sentence_break = overlap_text.find(". ")
        if sentence_break != -1:
            return overlap_text[sentence_break + 2:]

        # Try word boundary
        word_break = overlap_text.find(" ")
        if word_break != -1:
            return overlap_text[word_break + 1:]

        return overlap_text

    def _generate_chunk_id(self, content: str, document_id: str) -> str:
        """Generate unique chunk ID.

        Args:
            content: Chunk content
            document_id: Document identifier

        Returns:
            Unique chunk ID
        """
        hash_input = f"{document_id}:{content[:100]}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _is_section_header(self, item: TextItem, level: int) -> bool:
        """Check if item is a section header."""
        if hasattr(item, "label"):
            label = str(item.label).lower() if item.label else ""
            if "heading" in label or "title" in label:
                return True
        return level <= 2

    def _determine_element_type(self, item: Any, level: int) -> ElementType:
        """Determine element type from item."""
        if hasattr(item, "label"):
            label = str(item.label).lower() if item.label else ""
            if "heading" in label or "title" in label:
                return ElementType.HEADING
            if "list" in label:
                return ElementType.LIST
            if "code" in label:
                return ElementType.CODE
        return ElementType.TEXT

    def _extract_standard_code(self, text: str) -> Optional[IOSAStandardCode]:
        """Extract standard code from text."""
        import re

        pattern = r"^(ORG|FLT|DSP|MNT|CAB|GRH|CGO|SEC)\b"
        match = re.match(pattern, text.strip(), re.IGNORECASE)
        if match:
            try:
                return IOSAStandardCode(match.group(1).upper())
            except ValueError:
                pass
        return None

    def _get_page_number(self, item: Any) -> int:
        """Get page number from item."""
        if hasattr(item, "prov") and item.prov:
            return item.prov[0].page_no if item.prov[0].page_no else 0
        return 0

    def _table_in_section(
        self, table: Any, sections: List[Any]
    ) -> bool:
        """Check if table is already in a section."""
        for section in sections:
            if table.table_id in [t.table_id for t in section.tables]:
                return True
            for subsection in section.subsections:
                if self._table_in_section(table, [subsection]):
                    return True
        return False


def create_rag_chunks(
    document: DoclingDocument,
    config: Optional[IOSAConfig] = None,
) -> List[IOSAChunk]:
    """Convenience function to create RAG chunks from a document.

    Args:
        document: DoclingDocument to chunk
        config: Optional IOSA configuration

    Returns:
        List of chunks ready for RAG
    """
    if config is None:
        config = IOSAConfig()

    chunker = IOSAChunker(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )

    document_id = hashlib.md5(str(document).encode()).hexdigest()[:12]

    return chunker.chunk_document(
        document=document,
        document_id=document_id,
        source_file="",
    )
