"""
Parse endpoints for MMEL/MEL files.
"""

import os
import glob
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..models.schemas import ParseResponse

router = APIRouter(prefix="/parse", tags=["Parse"])

# Paths
MMEL_UPLOAD_DIR = "data/mmel"
MEL_UPLOAD_DIR = "data/mel"
OUTPUT_DIR = "output/parsed"


class FileInfo(BaseModel):
    filename: str
    path: str
    size_bytes: int


class FilesListResponse(BaseModel):
    mmel: List[FileInfo]
    mel: List[FileInfo]


class ParseAllResponse(BaseModel):
    status: str
    parsed: List[dict]
    errors: List[dict]
    message: str


def find_pdf_file(directory: str, file_id: str) -> Optional[str]:
    """
    Find a PDF file by ID or filename.

    Supports:
    - Full filename: "PC_12_MMEL_02395_1_8_4edcc764b4.pdf"
    - Filename without extension: "PC_12_MMEL_02395_1_8_4edcc764b4"
    - ID prefix pattern: "{file_id}_*.pdf"
    """
    # Try exact filename with .pdf
    exact_path = os.path.join(directory, f"{file_id}.pdf")
    if os.path.exists(exact_path):
        return exact_path

    # Try as-is (if already has .pdf)
    if file_id.endswith('.pdf'):
        exact_path = os.path.join(directory, file_id)
        if os.path.exists(exact_path):
            return exact_path

    # Try ID prefix pattern
    pattern = os.path.join(directory, f"{file_id}_*.pdf")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]

    # Try partial match
    for f in os.listdir(directory):
        if f.endswith('.pdf') and file_id in f:
            return os.path.join(directory, f)

    return None


def list_pdf_files(directory: str) -> List[FileInfo]:
    """List all PDF files in a directory."""
    files = []
    if os.path.exists(directory):
        for f in os.listdir(directory):
            if f.lower().endswith('.pdf'):
                path = os.path.join(directory, f)
                files.append(FileInfo(
                    filename=f,
                    path=path,
                    size_bytes=os.path.getsize(path)
                ))
    return files


def extract_pdf_to_markdown(pdf_path: str, output_path: str) -> int:
    """Extract PDF to markdown using pypdfium2."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_path)
    text_parts = []
    page_count = len(doc)

    for i, page in enumerate(doc):
        textpage = page.get_textpage()
        text = textpage.get_text_bounded()
        text_parts.append(f"## Page {i + 1}\n\n{text}\n")
        textpage.close()
        page.close()

    doc.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(text_parts))

    return page_count


def get_file_id_from_path(pdf_path: str) -> str:
    """Extract a clean file ID from a PDF path."""
    filename = os.path.basename(pdf_path)
    # Remove .pdf extension
    if filename.lower().endswith('.pdf'):
        filename = filename[:-4]
    return filename


@router.get("/files", response_model=FilesListResponse)
async def list_available_files():
    """
    List all available PDF files in data/mmel/ and data/mel/ directories.

    Returns both uploaded files and files copied via git.
    """
    return FilesListResponse(
        mmel=list_pdf_files(MMEL_UPLOAD_DIR),
        mel=list_pdf_files(MEL_UPLOAD_DIR)
    )


@router.post("/mmel/{file_id}", response_model=ParseResponse)
async def parse_mmel(file_id: str):
    """
    Parse a MMEL PDF file.

    1. Extracts text from PDF to markdown
    2. Runs the MMEL parser
    3. Returns structured JSON

    Args:
        file_id: The filename (with or without .pdf) or upload ID

    Examples:
        - POST /parse/mmel/PC_12_MMEL_02395_1_8_4edcc764b4
        - POST /parse/mmel/PC_12_MMEL_02395_1_8_4edcc764b4.pdf
    """
    # Find the PDF file
    pdf_path = find_pdf_file(MMEL_UPLOAD_DIR, file_id)
    if not pdf_path:
        # List available files for better error message
        available = [f.filename for f in list_pdf_files(MMEL_UPLOAD_DIR)]
        raise HTTPException(
            status_code=404,
            detail=f"MMEL file not found: {file_id}. Available: {available}"
        )

    # Use clean file ID for output naming
    clean_id = get_file_id_from_path(pdf_path)

    # Extract to markdown
    raw_output = os.path.join(OUTPUT_DIR, f"mmel_{clean_id}_raw.md")
    json_output = os.path.join(OUTPUT_DIR, f"mmel_{clean_id}_structured.json")

    try:
        page_count = extract_pdf_to_markdown(pdf_path, raw_output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")

    # Run the parser
    try:
        from mmel_tool.parser.mmel_parser import MmelParser
        parser = MmelParser(raw_output)
        items = parser.parse()
        stats = parser.get_statistics()

        # Save JSON output
        output_data = {
            'metadata': {
                'source_file': raw_output,
                'pdf_file': pdf_path,
                'total_items': stats['total_items'],
            },
            'statistics': stats,
            'items': items
        }
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

    return ParseResponse(
        status="success",
        file_id=clean_id,
        items_count=len(items),
        output_file=json_output,
        message=f"Parsed {len(items)} items from {page_count} pages",
        statistics=stats
    )


@router.post("/mel/{file_id}", response_model=ParseResponse)
async def parse_mel(file_id: str):
    """
    Parse a MEL PDF file.

    1. Extracts text from PDF to markdown
    2. Runs the MEL parser
    3. Returns structured JSON

    Args:
        file_id: The filename (with or without .pdf) or upload ID

    Examples:
        - POST /parse/mel/MEL_PC-12_ISS01_REV00
        - POST /parse/mel/MEL_PC-12_ISS01_REV00.pdf
    """
    # Find the PDF file
    pdf_path = find_pdf_file(MEL_UPLOAD_DIR, file_id)
    if not pdf_path:
        available = [f.filename for f in list_pdf_files(MEL_UPLOAD_DIR)]
        raise HTTPException(
            status_code=404,
            detail=f"MEL file not found: {file_id}. Available: {available}"
        )

    # Use clean file ID for output naming
    clean_id = get_file_id_from_path(pdf_path)

    # Extract to markdown
    raw_output = os.path.join(OUTPUT_DIR, f"mel_{clean_id}_raw.md")
    json_output = os.path.join(OUTPUT_DIR, f"mel_{clean_id}_structured.json")

    try:
        page_count = extract_pdf_to_markdown(pdf_path, raw_output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")

    # Run the parser
    try:
        from mmel_tool.parser.mel_parser import MelParser
        parser = MelParser(raw_output)
        items = parser.parse()
        stats = parser.get_statistics()

        # Save JSON output
        output_data = {
            'metadata': {
                'source_file': raw_output,
                'pdf_file': pdf_path,
                'total_items': stats['total_items'],
                'aircraft_registration': stats.get('aircraft_registration', ''),
                'aircraft_msn': stats.get('aircraft_msn', ''),
            },
            'statistics': stats,
            'items': items
        }
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

    return ParseResponse(
        status="success",
        file_id=clean_id,
        items_count=len(items),
        output_file=json_output,
        message=f"Parsed {len(items)} items from {page_count} pages",
        statistics=stats
    )


@router.post("/all", response_model=ParseAllResponse)
async def parse_all():
    """
    Parse ALL PDF files found in data/mmel/ and data/mel/ directories.

    Automatically detects and parses all PDFs, useful for batch processing.

    Returns:
        List of successfully parsed files and any errors
    """
    parsed = []
    errors = []

    # Parse all MMEL files
    for file_info in list_pdf_files(MMEL_UPLOAD_DIR):
        try:
            result = await parse_mmel(file_info.filename)
            parsed.append({
                "type": "mmel",
                "filename": file_info.filename,
                "items_count": result.items_count,
                "output_file": result.output_file
            })
        except HTTPException as e:
            errors.append({
                "type": "mmel",
                "filename": file_info.filename,
                "error": e.detail
            })
        except Exception as e:
            errors.append({
                "type": "mmel",
                "filename": file_info.filename,
                "error": str(e)
            })

    # Parse all MEL files
    for file_info in list_pdf_files(MEL_UPLOAD_DIR):
        try:
            result = await parse_mel(file_info.filename)
            parsed.append({
                "type": "mel",
                "filename": file_info.filename,
                "items_count": result.items_count,
                "output_file": result.output_file
            })
        except HTTPException as e:
            errors.append({
                "type": "mel",
                "filename": file_info.filename,
                "error": e.detail
            })
        except Exception as e:
            errors.append({
                "type": "mel",
                "filename": file_info.filename,
                "error": str(e)
            })

    return ParseAllResponse(
        status="success" if not errors else "partial",
        parsed=parsed,
        errors=errors,
        message=f"Parsed {len(parsed)} files, {len(errors)} errors"
    )


@router.get("/parsed")
async def list_parsed_files():
    """List all already-parsed JSON files in output/parsed/."""
    files = {"mmel": [], "mel": []}

    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith('_structured.json'):
                if f.startswith('mmel'):
                    files["mmel"].append(f)
                elif f.startswith('mel'):
                    files["mel"].append(f)

    return files
