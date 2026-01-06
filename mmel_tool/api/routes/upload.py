"""
Upload endpoints for PDF files.
"""

import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..models.schemas import UploadResponse

router = APIRouter(prefix="/upload", tags=["Upload"])

# Storage paths
MMEL_UPLOAD_DIR = "data/mmel"
MEL_UPLOAD_DIR = "data/mel"


def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


@router.post("/mmel", response_model=UploadResponse)
async def upload_mmel(file: UploadFile = File(...)):
    """
    Upload a MMEL PDF file.

    - Validates file is PDF
    - Saves to data/mmel/
    - Returns file_id for later reference
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    ensure_dir(MMEL_UPLOAD_DIR)

    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(MMEL_UPLOAD_DIR, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        status="uploaded",
        message=f"MMEL file uploaded successfully",
        file_path=file_path
    )


@router.post("/mel", response_model=UploadResponse)
async def upload_mel(file: UploadFile = File(...)):
    """
    Upload a MEL PDF file.

    - Validates file is PDF
    - Saves to data/mel/
    - Returns file_id for later reference
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    ensure_dir(MEL_UPLOAD_DIR)

    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(MEL_UPLOAD_DIR, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        status="uploaded",
        message=f"MEL file uploaded successfully",
        file_path=file_path
    )


@router.get("/files")
async def list_uploaded_files():
    """List all uploaded files."""
    files = {"mmel": [], "mel": []}

    if os.path.exists(MMEL_UPLOAD_DIR):
        files["mmel"] = [f for f in os.listdir(MMEL_UPLOAD_DIR) if f.endswith('.pdf')]

    if os.path.exists(MEL_UPLOAD_DIR):
        files["mel"] = [f for f in os.listdir(MEL_UPLOAD_DIR) if f.endswith('.pdf')]

    return files
