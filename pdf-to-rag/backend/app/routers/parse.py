"""FastAPI router for PDF parsing endpoints.

This module provides REST API endpoints for uploading and parsing PDF documents,
retrieving parsed documents, and querying blocks by page.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Union

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import Settings, get_settings
from app.models.document import (
    DocumentBlock,
    ParsedDocument,
    ParseRequest,
    ParseResponse,
    TableBlock,
)
from app.services.docling_service import DoclingService, get_docling_service

router = APIRouter(prefix="/parse", tags=["parsing"])

# In-memory cache for parsed documents (replace with Redis/DB in production)
_document_cache: dict[str, ParsedDocument] = {}


def _get_cache_path(settings: Settings, doc_id: str) -> Path:
    """Get the cache file path for a document.

    Args:
        settings: Application settings
        doc_id: Document ID

    Returns:
        Path to cache file
    """
    return settings.storage_path / f"{doc_id}.json"


def _save_document(settings: Settings, doc: ParsedDocument) -> None:
    """Save parsed document to cache and disk.

    Args:
        settings: Application settings
        doc: Parsed document to save
    """
    # Save to memory cache
    _document_cache[doc.id] = doc

    # Save to disk if storage path configured
    if settings.storage_path:
        cache_path = _get_cache_path(settings, doc.id)
        try:
            with open(cache_path, "w") as f:
                f.write(doc.model_dump_json(indent=2))
            logger.debug(f"Saved document {doc.id} to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save document to disk: {e}")


def _load_document(
    settings: Settings, doc_id: str
) -> Optional[ParsedDocument]:
    """Load parsed document from cache or disk.

    Args:
        settings: Application settings
        doc_id: Document ID

    Returns:
        ParsedDocument if found, None otherwise
    """
    # Check memory cache first
    if doc_id in _document_cache:
        return _document_cache[doc_id]

    # Try loading from disk
    if settings.storage_path:
        cache_path = _get_cache_path(settings, doc_id)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                doc = ParsedDocument.model_validate(data)
                _document_cache[doc_id] = doc  # Populate memory cache
                return doc
            except Exception as e:
                logger.warning(f"Failed to load document from disk: {e}")

    return None


@router.post(
    "",
    response_model=ParseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Parse a PDF document",
    description="Upload and parse a PDF document, extracting structured content with bounding boxes.",
)
async def parse_pdf(
    file: UploadFile = File(..., description="PDF file to parse"),
    extract_tables: bool = Query(True, description="Extract table structure"),
    extract_images: bool = Query(True, description="Extract image metadata"),
    ocr_enabled: bool = Query(True, description="Enable OCR for scanned documents"),
    settings: Settings = Depends(get_settings),
    docling_service: DoclingService = Depends(get_docling_service),
) -> ParseResponse:
    """Parse an uploaded PDF document.

    Uploads a PDF file and parses it using IBM Docling to extract:
    - Text blocks (paragraphs, titles, lists)
    - Tables with cell structure
    - Bounding boxes with normalized coordinates [0-1]
    - Hierarchical relationships between blocks

    Args:
        file: The PDF file to parse
        extract_tables: Whether to extract table structure
        extract_images: Whether to extract image metadata
        ocr_enabled: Whether to run OCR on scanned pages
        settings: Application settings
        docling_service: Docling parsing service

    Returns:
        ParseResponse containing the parsed document

    Raises:
        HTTPException: If file is invalid, too large, or parsing fails
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if not settings.is_extension_allowed(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {settings.allowed_extensions}",
        )

    # Read file content
    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file",
        )

    # Validate file size
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb} MB",
        )

    # Validate PDF header
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file",
        )

    logger.info(
        "Processing PDF upload",
        filename=file.filename,
        size_mb=len(file_bytes) / (1024 * 1024),
    )

    # Parse the document
    try:
        parsed_doc = docling_service.parse_pdf(
            file_bytes=file_bytes,
            filename=file.filename,
        )

        # Save to cache
        _save_document(settings, parsed_doc)

        return ParseResponse(success=True, document=parsed_doc)

    except ValueError as e:
        logger.error(f"PDF parsing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except TimeoutError:
        logger.error("PDF parsing timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF parsing timed out. Try a smaller document.",
        )
    except Exception as e:
        logger.exception("Unexpected error during PDF parsing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during parsing: {type(e).__name__}",
        )


@router.get(
    "/{doc_id}",
    response_model=ParsedDocument,
    summary="Get parsed document",
    description="Retrieve a previously parsed document by its ID.",
)
async def get_document(
    doc_id: str,
    settings: Settings = Depends(get_settings),
) -> ParsedDocument:
    """Retrieve a parsed document by ID.

    Args:
        doc_id: Unique document identifier
        settings: Application settings

    Returns:
        The parsed document

    Raises:
        HTTPException: If document not found
    """
    doc = _load_document(settings, doc_id)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {doc_id}",
        )

    return doc


@router.get(
    "/{doc_id}/page/{page_num}",
    response_model=list[Union[DocumentBlock, TableBlock]],
    summary="Get blocks for a specific page",
    description="Retrieve all content blocks for a specific page of a parsed document.",
)
async def get_page_blocks(
    doc_id: str,
    page_num: int,
    include_hidden: bool = Query(False, description="Include hidden blocks"),
    settings: Settings = Depends(get_settings),
) -> list[Union[DocumentBlock, TableBlock]]:
    """Retrieve all blocks for a specific page.

    Args:
        doc_id: Document identifier
        page_num: Page number (1-indexed)
        include_hidden: Whether to include soft-deleted blocks
        settings: Application settings

    Returns:
        List of blocks on the specified page

    Raises:
        HTTPException: If document or page not found
    """
    doc = _load_document(settings, doc_id)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {doc_id}",
        )

    if page_num < 1 or page_num > doc.total_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid page number. Document has {doc.total_pages} pages.",
        )

    blocks = doc.get_blocks_by_page(page_num)

    if not include_hidden:
        blocks = [b for b in blocks if not b.hidden]

    return blocks


@router.get(
    "/{doc_id}/blocks",
    response_model=list[Union[DocumentBlock, TableBlock]],
    summary="Get blocks by type",
    description="Retrieve blocks filtered by type (title, paragraph, table, etc.).",
)
async def get_blocks_by_type(
    doc_id: str,
    block_type: Optional[str] = Query(None, description="Filter by block type"),
    page: Optional[int] = Query(None, ge=1, description="Filter by page number"),
    include_hidden: bool = Query(False, description="Include hidden blocks"),
    settings: Settings = Depends(get_settings),
) -> list[Union[DocumentBlock, TableBlock]]:
    """Retrieve blocks with optional filters.

    Args:
        doc_id: Document identifier
        block_type: Filter by block type (title, paragraph, table, etc.)
        page: Filter by page number
        include_hidden: Whether to include soft-deleted blocks
        settings: Application settings

    Returns:
        List of matching blocks

    Raises:
        HTTPException: If document not found
    """
    doc = _load_document(settings, doc_id)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {doc_id}",
        )

    blocks = doc.blocks

    # Apply filters
    if block_type:
        blocks = [b for b in blocks if b.type == block_type]

    if page:
        blocks = [b for b in blocks if b.bbox.page == page]

    if not include_hidden:
        blocks = [b for b in blocks if not b.hidden]

    return blocks


@router.patch(
    "/{doc_id}/blocks/{block_id}",
    response_model=Union[DocumentBlock, TableBlock],
    summary="Update a block",
    description="Update block properties (e.g., hide, keep_with_next).",
)
async def update_block(
    doc_id: str,
    block_id: str,
    hidden: Optional[bool] = Query(None, description="Set hidden status"),
    keep_with_next: Optional[bool] = Query(None, description="Set keep_with_next"),
    settings: Settings = Depends(get_settings),
) -> Union[DocumentBlock, TableBlock]:
    """Update block properties.

    Args:
        doc_id: Document identifier
        block_id: Block identifier
        hidden: New hidden status
        keep_with_next: New keep_with_next status
        settings: Application settings

    Returns:
        Updated block

    Raises:
        HTTPException: If document or block not found
    """
    doc = _load_document(settings, doc_id)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {doc_id}",
        )

    # Find the block
    block = None
    for b in doc.blocks:
        if b.id == block_id:
            block = b
            break

    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block not found: {block_id}",
        )

    # Update properties
    if hidden is not None:
        block.hidden = hidden

    if keep_with_next is not None:
        block.keep_with_next = keep_with_next

    # Save updated document
    _save_document(settings, doc)

    return block


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a parsed document",
    description="Remove a parsed document from cache and storage.",
)
async def delete_document(
    doc_id: str,
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete a parsed document.

    Args:
        doc_id: Document identifier
        settings: Application settings

    Raises:
        HTTPException: If document not found
    """
    # Check if document exists
    doc = _load_document(settings, doc_id)

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {doc_id}",
        )

    # Remove from memory cache
    if doc_id in _document_cache:
        del _document_cache[doc_id]

    # Remove from disk
    cache_path = _get_cache_path(settings, doc_id)
    if cache_path.exists():
        try:
            cache_path.unlink()
            logger.info(f"Deleted document {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to delete document file: {e}")


@router.get(
    "",
    response_model=list[dict],
    summary="List all parsed documents",
    description="Get a list of all parsed documents with basic metadata.",
)
async def list_documents(
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """List all parsed documents.

    Returns basic metadata for all cached documents.

    Args:
        settings: Application settings

    Returns:
        List of document summaries
    """
    documents = []

    # Check disk storage for all documents
    if settings.storage_path.exists():
        for cache_file in settings.storage_path.glob("*.json"):
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                documents.append({
                    "id": data.get("id"),
                    "filename": data.get("filename"),
                    "total_pages": data.get("total_pages"),
                    "block_count": len(data.get("blocks", [])),
                    "created_at": data.get("created_at"),
                    "processing_time_ms": data.get("processing_time_ms"),
                })
            except Exception as e:
                logger.debug(f"Failed to read cache file {cache_file}: {e}")

    return documents
