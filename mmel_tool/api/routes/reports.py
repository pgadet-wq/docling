"""
Reports and items endpoints.
"""

import os
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from ..models.schemas import ItemsListResponse

router = APIRouter(tags=["Items"])

# Default file paths (can be overridden)
DEFAULT_MMEL_FILE = "output/parsed/mmel_pc12_structured.json"
DEFAULT_MEL_FILE = "output/parsed/mel_pc12_structured.json"


def load_json_file(path: str) -> dict:
    """Load a JSON file."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.get("/items/mmel", response_model=ItemsListResponse)
async def list_mmel_items(
    file_path: str = Query(DEFAULT_MMEL_FILE, description="Path to MMEL JSON file"),
    ata_chapter: Optional[str] = Query(None, description="Filter by ATA chapter (e.g., '21')"),
    interval: Optional[str] = Query(None, description="Filter by rectification interval (A/B/C/D)"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type (CAT/NCO/SPO/ALL)"),
    search: Optional[str] = Query(None, description="Search in item code or title"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List MMEL items with optional filtering.

    Filters:
    - ata_chapter: Filter by ATA chapter number
    - interval: Filter by rectification interval (A, B, C, D)
    - operation_type: Filter by operation type (CAT, NCO, SPO, ALL)
    - search: Search in item code or title
    """
    data = load_json_file(file_path)
    items = data.get('items', [])

    filters_applied = {}

    # Apply filters
    if ata_chapter:
        items = [i for i in items if i.get('ataChapter') == ata_chapter]
        filters_applied['ata_chapter'] = ata_chapter

    if interval:
        items = [i for i in items if i.get('rectificationInterval') == interval.upper()]
        filters_applied['interval'] = interval.upper()

    if operation_type:
        op = operation_type.upper()
        items = [i for i in items if op in i.get('operationTypes', [])]
        filters_applied['operation_type'] = op

    if search:
        search_lower = search.lower()
        items = [i for i in items if
                 search_lower in i.get('fullItemCode', '').lower() or
                 search_lower in i.get('itemTitle', '').lower()]
        filters_applied['search'] = search

    total = len(items)

    # Apply pagination
    items = items[offset:offset + limit]

    return ItemsListResponse(
        total_items=total,
        filters_applied=filters_applied,
        items=items
    )


@router.get("/items/mel", response_model=ItemsListResponse)
async def list_mel_items(
    file_path: str = Query(DEFAULT_MEL_FILE, description="Path to MEL JSON file"),
    ata_chapter: Optional[str] = Query(None, description="Filter by ATA chapter (e.g., '21')"),
    category: Optional[str] = Query(None, description="Filter by category (A/B/C/D)"),
    search: Optional[str] = Query(None, description="Search in item code or title"),
    maintenance_required: Optional[bool] = Query(None, description="Filter by (M) flag"),
    operations_required: Optional[bool] = Query(None, description="Filter by (O) flag"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List MEL items with optional filtering.

    Filters:
    - ata_chapter: Filter by ATA chapter number
    - category: Filter by category (A, B, C, D)
    - search: Search in item code or title
    - maintenance_required: Filter by (M) flag
    - operations_required: Filter by (O) flag
    """
    data = load_json_file(file_path)
    items = data.get('items', [])

    filters_applied = {}

    # Apply filters
    if ata_chapter:
        items = [i for i in items if i.get('ataChapter') == ata_chapter]
        filters_applied['ata_chapter'] = ata_chapter

    if category:
        items = [i for i in items if i.get('category') == category.upper()]
        filters_applied['category'] = category.upper()

    if search:
        search_lower = search.lower()
        items = [i for i in items if
                 search_lower in i.get('fullItemCode', '').lower() or
                 search_lower in i.get('itemTitle', '').lower()]
        filters_applied['search'] = search

    if maintenance_required is not None:
        items = [i for i in items if i.get('requiresMaintenance') == maintenance_required]
        filters_applied['maintenance_required'] = maintenance_required

    if operations_required is not None:
        items = [i for i in items if i.get('requiresOperations') == operations_required]
        filters_applied['operations_required'] = operations_required

    total = len(items)

    # Apply pagination
    items = items[offset:offset + limit]

    return ItemsListResponse(
        total_items=total,
        filters_applied=filters_applied,
        items=items
    )


@router.get("/items/mmel/{item_code}")
async def get_mmel_item(
    item_code: str,
    file_path: str = Query(DEFAULT_MMEL_FILE),
):
    """Get a specific MMEL item by code."""
    data = load_json_file(file_path)
    items = data.get('items', [])

    for item in items:
        if item.get('fullItemCode') == item_code:
            return item

    raise HTTPException(status_code=404, detail=f"Item not found: {item_code}")


@router.get("/items/mel/{item_code}")
async def get_mel_item(
    item_code: str,
    file_path: str = Query(DEFAULT_MEL_FILE),
):
    """Get a specific MEL item by code."""
    data = load_json_file(file_path)
    items = data.get('items', [])

    for item in items:
        if item.get('fullItemCode') == item_code:
            return item

    raise HTTPException(status_code=404, detail=f"Item not found: {item_code}")


@router.get("/statistics/mmel")
async def get_mmel_statistics(
    file_path: str = Query(DEFAULT_MMEL_FILE),
):
    """Get MMEL statistics."""
    data = load_json_file(file_path)
    return {
        "metadata": data.get('metadata', {}),
        "statistics": data.get('statistics', {}),
    }


@router.get("/statistics/mel")
async def get_mel_statistics(
    file_path: str = Query(DEFAULT_MEL_FILE),
):
    """Get MEL statistics."""
    data = load_json_file(file_path)
    return {
        "metadata": data.get('metadata', {}),
        "statistics": data.get('statistics', {}),
    }
