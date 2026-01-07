# PDF-to-RAG Backend

Backend API for parsing PDF documents using IBM Docling, designed for RAG (Retrieval-Augmented Generation) applications. Extracts structured content with bounding boxes for visual synchronization.

## Features

- **PDF Parsing**: Extract structured content from PDF documents using IBM Docling
- **Bounding Boxes**: Normalized coordinates [0-1] for all content blocks
- **Table Extraction**: TableFormer-based table structure extraction with cell data
- **Hierarchical Structure**: Parent-child relationships between blocks (headings → content)
- **GPU Acceleration**: Optional CUDA support for faster processing
- **Large Document Support**: Optimized for documents up to 1000 pages

## Project Structure

```
pdf-to-rag/
├── docker/
│   ├── Dockerfile           # Multi-stage build (CPU/GPU variants)
│   └── docker-compose.yml   # Docker Compose configuration
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI application
│   │   ├── config.py        # Pydantic settings
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── document.py  # Pydantic models (BoundingBox, DocumentBlock, etc.)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── docling_service.py  # IBM Docling integration
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── parse.py     # API endpoints
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py      # Pytest fixtures
│   │   └── test_parse.py    # API tests
│   └── requirements.txt
└── README.md
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- NVIDIA GPU + CUDA (optional, for GPU acceleration)

### Using Docker (Recommended)

**CPU Mode:**
```bash
cd pdf-to-rag
docker-compose -f docker/docker-compose.yml up pdf-to-rag-cpu
```

**GPU Mode (requires NVIDIA Docker):**
```bash
cd pdf-to-rag
docker-compose -f docker/docker-compose.yml --profile gpu up pdf-to-rag-gpu
```

The API will be available at `http://localhost:8000`.

### Local Development

1. **Create virtual environment:**
   ```bash
   cd pdf-to-rag/backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or: venv\Scripts\activate  # Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Endpoints

#### Parse PDF
```http
POST /api/v1/parse
Content-Type: multipart/form-data

file: <PDF file>
extract_tables: true (optional)
extract_images: true (optional)
ocr_enabled: true (optional)
```

**Response:**
```json
{
  "success": true,
  "document": {
    "id": "uuid",
    "filename": "document.pdf",
    "total_pages": 10,
    "blocks": [...],
    "pages": [...],
    "metadata": {},
    "created_at": "2024-01-01T00:00:00Z",
    "processing_time_ms": 1500
  }
}
```

#### Get Document
```http
GET /api/v1/parse/{doc_id}
```

#### Get Page Blocks
```http
GET /api/v1/parse/{doc_id}/page/{page_num}?include_hidden=false
```

#### Filter Blocks
```http
GET /api/v1/parse/{doc_id}/blocks?block_type=table&page=1
```

#### List Documents
```http
GET /api/v1/parse
```

#### Delete Document
```http
DELETE /api/v1/parse/{doc_id}
```

#### Health Check
```http
GET /api/v1/health
```

## Data Models

### BoundingBox
```python
{
  "x0": 0.1,   # Left (normalized 0-1)
  "y0": 0.2,   # Top (normalized 0-1)
  "x1": 0.9,   # Right (normalized 0-1)
  "y1": 0.3,   # Bottom (normalized 0-1)
  "page": 1   # Page number (1-indexed)
}
```

### DocumentBlock
```python
{
  "id": "uuid",
  "type": "paragraph",  # title, paragraph, table, list, image, header, footer, caption
  "text": "Content text",
  "bbox": {...},
  "level": 1,           # For titles (1-6)
  "parent_id": "uuid",  # Parent block ID
  "children_ids": [],
  "confidence": 0.95,   # OCR confidence
  "metadata": {},
  "hidden": false,
  "keep_with_next": false
}
```

### TableBlock
```python
{
  "id": "uuid",
  "type": "table",
  "text": "Flattened table text",
  "bbox": {...},
  "rows": 5,
  "cols": 3,
  "cells": [
    {
      "row": 0,
      "col": 0,
      "row_span": 1,
      "col_span": 1,
      "text": "Cell content",
      "is_header": true
    }
  ]
}
```

## Configuration

Configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_GPU` | `false` | Enable GPU acceleration |
| `DEVICE` | `cpu` | Device: `cpu`, `cuda`, `mps` |
| `MAX_FILE_SIZE_MB` | `100` | Maximum upload size |
| `STORAGE_PATH` | `/app/storage` | Document cache path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DOCLING_OCR_ENABLED` | `true` | Enable OCR |
| `DOCLING_TABLE_EXTRACTION` | `true` | Enable table extraction |
| `MAX_PAGES` | `1000` | Maximum pages to process |
| `PROCESSING_TIMEOUT_SECONDS` | `600` | Processing timeout |

## Performance Considerations

### Large Documents (700+ pages)
- GPU mode recommended for documents over 100 pages
- Processing time scales linearly with page count
- Memory usage: ~50MB per 100 pages

### Scaleway Deployment
- **CPU**: DEV1-L or higher (8GB RAM minimum)
- **GPU**: GPU-3070-S or higher for production workloads
- Enable swap for very large documents

## Example Usage

### Python Client
```python
import httpx

# Upload and parse PDF
with open("document.pdf", "rb") as f:
    response = httpx.post(
        "http://localhost:8000/api/v1/parse",
        files={"file": ("document.pdf", f, "application/pdf")},
    )
    result = response.json()
    doc_id = result["document"]["id"]

# Get blocks for page 1
response = httpx.get(f"http://localhost:8000/api/v1/parse/{doc_id}/page/1")
blocks = response.json()

for block in blocks:
    print(f"[{block['type']}] {block['text'][:50]}...")
    print(f"  Position: ({block['bbox']['x0']:.2f}, {block['bbox']['y0']:.2f})")
```

### cURL
```bash
# Upload PDF
curl -X POST "http://localhost:8000/api/v1/parse" \
  -F "file=@document.pdf"

# Get document
curl "http://localhost:8000/api/v1/parse/{doc_id}"

# Get tables only
curl "http://localhost:8000/api/v1/parse/{doc_id}/blocks?block_type=table"
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_parse.py -v
```

## License

This project uses IBM Docling which is licensed under MIT License.
