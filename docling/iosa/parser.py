"""IOSA Document Parser
======================

Main parser class that orchestrates IOSA document processing.
Combines hybrid pipeline, standards extraction, and chunking.
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableStructureOptions,
    ThreadedPdfPipelineOptions,
)
from docling.iosa.chunking import IOSAChunker
from docling.iosa.config import IOSAConfig, OutputFormat, TableMode
from docling.iosa.extractor import IOSAExtractor, IOSAStandard
from docling.iosa.models import (
    DocumentMetadata,
    IOSAChunk,
    IOSADocument,
    IOSAParseResult,
    IOSAStandardCode,
    TableExtractionResult,
)

_log = logging.getLogger(__name__)


class IOSAParser:
    """Main parser for IOSA aviation documents.

    This parser provides:
    - Hybrid PDF parsing (standard + VLM for tables)
    - IOSA standards extraction
    - Multiple output formats (JSON, Markdown, HTML)
    - RAG-ready chunking

    Example:
        parser = IOSAParser(config=IOSAConfig(
            vlm_model="pgadet-wq/granite-docling-258M",
            device="cuda"
        ))
        result = parser.parse("iosa_manual.pdf")
        print(result.document.markdown)
    """

    def __init__(self, config: Optional[IOSAConfig] = None):
        """Initialize the parser.

        Args:
            config: IOSA configuration (uses defaults if None)
        """
        self.config = config or IOSAConfig()

        # Initialize components
        self._converter: Optional[DocumentConverter] = None
        self._extractor: Optional[IOSAExtractor] = None
        self._chunker: Optional[IOSAChunker] = None

        # Lazy initialization flag
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy initialize components."""
        if self._initialized:
            return

        _log.info("Initializing IOSA parser...")

        # Create pipeline options
        pipeline_options = self._create_pipeline_options()

        # Initialize document converter
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )

        # Initialize extractor
        target_standards = None
        if self.config.standard_codes:
            target_standards = [
                IOSAStandard(code) for code in self.config.standard_codes
            ]
        self._extractor = IOSAExtractor(target_standards=target_standards)

        # Initialize chunker
        if self.config.enable_chunking:
            self._chunker = IOSAChunker(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )

        self._initialized = True
        _log.info("IOSA parser initialized")

    def _create_pipeline_options(self) -> PdfPipelineOptions:
        """Create pipeline options from config."""
        table_options = TableStructureOptions(
            mode="accurate" if self.config.table_mode != TableMode.STANDARD else "fast",
            do_cell_matching=True,
        )

        return ThreadedPdfPipelineOptions(
            do_table_structure=True,
            table_structure_options=table_options,
            do_ocr=self.config.enable_ocr,
            images_scale=self.config.images_scale,
            generate_page_images=self.config.table_mode != TableMode.STANDARD,
            generate_table_images=True,
        )

    def parse(
        self,
        source: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
    ) -> IOSAParseResult:
        """Parse an IOSA document.

        Args:
            source: Path to PDF file or URL
            output_dir: Optional directory for output files

        Returns:
            IOSAParseResult with document, chunks, and outputs
        """
        self._initialize()

        start_time = time.time()
        errors: List[str] = []
        warnings: List[str] = []

        _log.info(f"Parsing document: {source}")

        try:
            # Convert document
            conv_result = self._convert_document(source)

            if conv_result.status == ConversionStatus.FAILURE:
                return IOSAParseResult(
                    success=False,
                    errors=[f"Document conversion failed: {conv_result.errors}"],
                )

            # Extract document info
            docling_doc = conv_result.document
            if docling_doc is None:
                return IOSAParseResult(
                    success=False,
                    errors=["No document produced from conversion"],
                )

            # Create IOSA document
            iosa_doc = self._create_iosa_document(
                conv_result, source, start_time
            )

            # Extract standards
            if self.config.extract_standards and self._extractor:
                compliance_items, sections = self._extractor.extract_from_document(
                    docling_doc
                )
                iosa_doc.compliance_items = compliance_items
                iosa_doc.sections = sections

                # Update metadata with found standards
                found_codes = set()
                for item in compliance_items:
                    found_codes.add(item.standard_code)
                iosa_doc.metadata.standard_codes_found = list(found_codes)

            # Extract tables
            tables = self._extract_tables(conv_result)
            iosa_doc.tables = tables
            iosa_doc.metadata.table_count = len(tables)

            # Generate outputs
            iosa_doc.markdown = docling_doc.export_to_markdown()
            iosa_doc.raw_text = docling_doc.export_to_text()

            # Create chunks
            chunks: List[IOSAChunk] = []
            if self.config.enable_chunking and self._chunker:
                chunks = self._chunker.chunk_document(
                    docling_doc,
                    iosa_doc.metadata.document_id,
                    str(source),
                )

            # Calculate processing time
            processing_time = time.time() - start_time
            iosa_doc.metadata.processing_time_seconds = processing_time

            # Create result
            result = IOSAParseResult(
                success=True,
                document=iosa_doc,
                chunks=chunks,
                errors=errors,
                warnings=warnings,
                processing_stats={
                    "processing_time_seconds": processing_time,
                    "total_pages": iosa_doc.metadata.total_pages,
                    "table_count": len(tables),
                    "chunk_count": len(chunks),
                    "compliance_items_count": len(iosa_doc.compliance_items),
                },
            )

            # Save outputs if output_dir specified
            if output_dir:
                self._save_outputs(result, output_dir)

            _log.info(
                f"Parsing complete in {processing_time:.2f}s. "
                f"Pages: {iosa_doc.metadata.total_pages}, "
                f"Tables: {len(tables)}, "
                f"Chunks: {len(chunks)}"
            )

            return result

        except Exception as e:
            _log.exception(f"Error parsing document: {e}")
            return IOSAParseResult(
                success=False,
                errors=[str(e)],
            )

    def _convert_document(
        self, source: Union[str, Path]
    ) -> ConversionResult:
        """Convert document using Docling.

        Args:
            source: Document source

        Returns:
            ConversionResult
        """
        if self._converter is None:
            raise RuntimeError("Parser not initialized")

        source_path = Path(source) if isinstance(source, str) else source
        return self._converter.convert(source_path)

    def _create_iosa_document(
        self,
        conv_result: ConversionResult,
        source: Union[str, Path],
        start_time: float,
    ) -> IOSADocument:
        """Create IOSADocument from conversion result.

        Args:
            conv_result: Docling conversion result
            source: Document source
            start_time: Processing start time

        Returns:
            IOSADocument
        """
        source_path = Path(source) if isinstance(source, str) else source

        # Generate document ID
        doc_id = hashlib.md5(
            f"{source_path.name}:{start_time}".encode()
        ).hexdigest()[:12]

        # Get file info
        file_size = 0
        if source_path.exists():
            file_size = source_path.stat().st_size

        # Count pages
        total_pages = len(conv_result.pages) if conv_result.pages else 0

        # Detect document type from filename
        doc_type = self._detect_document_type(source_path.name)

        metadata = DocumentMetadata(
            document_id=doc_id,
            filename=source_path.name,
            document_type=doc_type,
            total_pages=total_pages,
            file_size_bytes=file_size,
            created_at=datetime.utcnow(),
        )

        return IOSADocument(metadata=metadata)

    def _detect_document_type(self, filename: str) -> str:
        """Detect document type from filename.

        Args:
            filename: File name

        Returns:
            Document type string
        """
        filename_lower = filename.lower()

        if "mmel" in filename_lower:
            return "MMEL"  # Master Minimum Equipment List
        if "mel" in filename_lower:
            return "MEL"  # Minimum Equipment List
        if "iosa" in filename_lower:
            return "IOSA Standards Manual"
        if "isarp" in filename_lower:
            return "ISARP"  # IATA Standards and Recommended Practices
        if "fcom" in filename_lower:
            return "FCOM"  # Flight Crew Operating Manual
        if "qrh" in filename_lower:
            return "QRH"  # Quick Reference Handbook
        if "afm" in filename_lower:
            return "AFM"  # Aircraft Flight Manual

        return "Aviation Document"

    def _extract_tables(
        self, conv_result: ConversionResult
    ) -> List[TableExtractionResult]:
        """Extract tables from conversion result.

        Args:
            conv_result: Conversion result

        Returns:
            List of TableExtractionResult
        """
        tables: List[TableExtractionResult] = []

        if conv_result.document is None:
            return tables

        from docling_core.types.doc import TableItem

        table_idx = 0
        for item, _ in conv_result.document.iterate_items():
            if isinstance(item, TableItem):
                try:
                    # Get table info
                    page_no = 0
                    if hasattr(item, "prov") and item.prov:
                        page_no = item.prov[0].page_no if item.prov[0].page_no else 0

                    # Export table
                    table_md = ""
                    table_html = ""
                    try:
                        table_md = item.export_to_markdown()
                        table_html = item.export_to_html()
                    except Exception:
                        pass

                    # Count rows and cols
                    rows = 0
                    cols = 0
                    cells = []
                    if hasattr(item, "data") and item.data:
                        if hasattr(item.data, "num_rows"):
                            rows = item.data.num_rows
                        if hasattr(item.data, "num_cols"):
                            cols = item.data.num_cols

                    table_result = TableExtractionResult(
                        table_id=f"table_{table_idx}",
                        page_number=page_no,
                        rows=rows,
                        cols=cols,
                        cells=cells,
                        html=table_html,
                        markdown=table_md,
                        extraction_method=(
                            "vlm" if self.config.table_mode == TableMode.VLM else "standard"
                        ),
                    )
                    tables.append(table_result)
                    table_idx += 1

                except Exception as e:
                    _log.warning(f"Error extracting table: {e}")

        return tables

    def _save_outputs(
        self,
        result: IOSAParseResult,
        output_dir: Union[str, Path],
    ) -> None:
        """Save outputs to files.

        Args:
            result: Parse result
            output_dir: Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if result.document is None:
            return

        base_name = Path(result.document.metadata.filename).stem

        # Save JSON
        if OutputFormat.JSON in self.config.output_formats or OutputFormat.ALL in self.config.output_formats:
            json_path = output_path / f"{base_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result.document.model_dump(), f, indent=2, default=str)
            result.json_output = str(json_path)

        # Save Markdown
        if OutputFormat.MARKDOWN in self.config.output_formats or OutputFormat.ALL in self.config.output_formats:
            md_path = output_path / f"{base_name}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(result.document.markdown)
            result.markdown_output = str(md_path)

        # Save HTML
        if OutputFormat.HTML in self.config.output_formats or OutputFormat.ALL in self.config.output_formats:
            html_path = output_path / f"{base_name}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(result.document.html or self._markdown_to_html(result.document.markdown))
            result.html_output = str(html_path)

        # Save chunks
        if (OutputFormat.CHUNKS in self.config.output_formats or OutputFormat.ALL in self.config.output_formats) and result.chunks:
            chunks_path = output_path / f"{base_name}_chunks.json"
            chunks_data = [chunk.model_dump() for chunk in result.chunks]
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks_data, f, indent=2, default=str)
            result.chunks_output = str(chunks_path)

        _log.info(f"Outputs saved to {output_path}")

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML.

        Args:
            markdown: Markdown content

        Returns:
            HTML content
        """
        try:
            import marko

            return marko.convert(markdown)
        except ImportError:
            # Fallback: wrap in pre tag
            return f"<html><body><pre>{markdown}</pre></body></html>"

    def get_stats(self) -> Dict[str, Any]:
        """Get parser statistics.

        Returns:
            Parser statistics
        """
        return {
            "initialized": self._initialized,
            "config": self.config.model_dump(),
        }


def parse_iosa_document(
    source: Union[str, Path],
    config: Optional[IOSAConfig] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> IOSAParseResult:
    """Convenience function to parse an IOSA document.

    Args:
        source: Path to PDF file
        config: Optional configuration
        output_dir: Optional output directory

    Returns:
        IOSAParseResult
    """
    parser = IOSAParser(config=config)
    return parser.parse(source, output_dir=output_dir)
