"""
Parse endpoints for MMEL/MEL files.
"""

import os
import glob
from fastapi import APIRouter, HTTPException
from ..models.schemas import ParseResponse

router = APIRouter(prefix="/parse", tags=["Parse"])

# Paths
MMEL_UPLOAD_DIR = "data/mmel"
MEL_UPLOAD_DIR = "data/mel"
OUTPUT_DIR = "output/parsed"


def find_file_by_id(directory: str, file_id: str) -> str:
    """Find a file by its ID prefix."""
    pattern = os.path.join(directory, f"{file_id}_*.pdf")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]


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


@router.post("/mmel/{file_id}", response_model=ParseResponse)
async def parse_mmel(file_id: str):
    """
    Parse a MMEL PDF file.

    1. Extracts text from PDF to markdown
    2. Runs the MMEL parser
    3. Returns structured JSON

    Args:
        file_id: The ID returned from upload
    """
    # Find the PDF file
    pdf_path = find_file_by_id(MMEL_UPLOAD_DIR, file_id)
    if not pdf_path:
        raise HTTPException(status_code=404, detail=f"MMEL file not found: {file_id}")

    # Extract to markdown
    raw_output = os.path.join(OUTPUT_DIR, f"mmel_{file_id}_raw.md")
    json_output = os.path.join(OUTPUT_DIR, f"mmel_{file_id}_structured.json")

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
        import json
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
        file_id=file_id,
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
        file_id: The ID returned from upload
    """
    # Find the PDF file
    pdf_path = find_file_by_id(MEL_UPLOAD_DIR, file_id)
    if not pdf_path:
        raise HTTPException(status_code=404, detail=f"MEL file not found: {file_id}")

    # Extract to markdown
    raw_output = os.path.join(OUTPUT_DIR, f"mel_{file_id}_raw.md")
    json_output = os.path.join(OUTPUT_DIR, f"mel_{file_id}_structured.json")

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
        import json
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
        file_id=file_id,
        items_count=len(items),
        output_file=json_output,
        message=f"Parsed {len(items)} items from {page_count} pages",
        statistics=stats
    )


@router.get("/files")
async def list_parsed_files():
    """List all parsed files."""
    files = {"mmel": [], "mel": []}

    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith('_structured.json'):
                if f.startswith('mmel'):
                    files["mmel"].append(f)
                elif f.startswith('mel'):
                    files["mel"].append(f)

    return files
