"""API Routes."""

from .upload import router as upload_router
from .parse import router as parse_router
from .audit import router as audit_router
from .reports import router as reports_router
from .chat import router as chat_router

__all__ = [
    "upload_router",
    "parse_router",
    "audit_router",
    "reports_router",
    "chat_router",
]
