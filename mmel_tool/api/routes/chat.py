"""
Chat endpoint for MEL/MMEL conversational AI.
"""

import os
import glob
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat"])

# Paths
PARSED_DIR = "output/parsed"

# Global assistant instance (lazy loaded)
_assistant = None


class ChatRequest(BaseModel):
    question: str
    include_history: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]


class DispatchRequest(BaseModel):
    item_code: str


class DispatchResponse(BaseModel):
    item_code: str
    can_dispatch: bool
    conditions: List[str]
    rectification_interval: Optional[str]
    remarks: Optional[str]
    source: Optional[str]
    description: Optional[str]
    ai_explanation: Optional[str]
    error: Optional[str] = None


def get_assistant():
    """Get or create the assistant instance."""
    global _assistant

    if _assistant is not None:
        return _assistant

    # Find latest parsed files
    mmel_files = glob.glob(os.path.join(PARSED_DIR, "mmel_*_structured.json"))
    mel_files = glob.glob(os.path.join(PARSED_DIR, "mel_*_structured.json"))
    audit_files = glob.glob("output/audit/audit_*.json")

    if not mmel_files or not mel_files:
        raise HTTPException(
            status_code=404,
            detail="No parsed files found. Run POST /api/v1/parse/all first."
        )

    mmel_file = max(mmel_files, key=os.path.getmtime)
    mel_file = max(mel_files, key=os.path.getmtime)
    audit_file = max(audit_files, key=os.path.getmtime) if audit_files else None

    try:
        from mmel_tool.mistral.assistant import MmelAssistant
        _assistant = MmelAssistant(
            mmel_data=mmel_file,
            mel_data=mel_file,
            audit_data=audit_file,
        )
        return _assistant
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize assistant: {str(e)}. Check MISTRAL_API_KEY."
        )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Ask a question about MEL/MMEL data.

    Examples:
        - "Puis-je décoller sans le FMS ?"
        - "Quels sont les items non conformes ?"
        - "Explique-moi l'item 34-50-01A"

    Args:
        request: ChatRequest with question and optional history flag

    Returns:
        AI response with sources
    """
    assistant = get_assistant()

    try:
        answer = assistant.ask(request.question, include_history=request.include_history)
        sources = assistant.get_sources(answer)

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/dispatch", response_model=DispatchResponse)
async def check_dispatch(request: DispatchRequest):
    """
    Check if dispatch is possible with an inoperative item.

    Args:
        request: DispatchRequest with item_code

    Returns:
        Dispatch decision with details
    """
    assistant = get_assistant()

    try:
        result = assistant.can_dispatch(request.item_code)
        return DispatchResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dispatch check failed: {str(e)}")


@router.get("/explain/{item_code}")
async def explain_item(item_code: str):
    """
    Get detailed explanation of an item.

    Args:
        item_code: The MEL/MMEL item code (e.g., "34-50-01A")

    Returns:
        Detailed explanation
    """
    assistant = get_assistant()

    try:
        explanation = assistant.explain_item(item_code)
        sources = assistant.get_sources(explanation)

        return {"item_code": item_code, "explanation": explanation, "sources": sources}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")


@router.get("/compare/{item_code}")
async def compare_item(item_code: str):
    """
    Compare MEL vs MMEL for a specific item.

    Args:
        item_code: The item code to compare

    Returns:
        Comparison analysis
    """
    assistant = get_assistant()

    try:
        comparison = assistant.compare_items(item_code)
        sources = assistant.get_sources(comparison)

        return {"item_code": item_code, "comparison": comparison, "sources": sources}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/non-compliant-summary")
async def non_compliant_summary():
    """
    Get a summary of non-compliant items.

    Returns:
        Summary of non-conformities
    """
    assistant = get_assistant()

    try:
        summary = assistant.get_non_compliant_summary()
        sources = assistant.get_sources(summary)

        return {"summary": summary, "sources": sources}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")


@router.post("/clear-history")
async def clear_history():
    """Clear conversation history."""
    global _assistant

    if _assistant:
        _assistant.clear_history()

    return {"status": "success", "message": "Conversation history cleared"}
