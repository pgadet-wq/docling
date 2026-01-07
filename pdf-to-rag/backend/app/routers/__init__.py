"""FastAPI routers for the PDF-to-RAG API."""

from app.routers.parse import router as parse_router

__all__ = ["parse_router"]
