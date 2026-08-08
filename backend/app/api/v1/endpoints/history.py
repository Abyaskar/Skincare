"""
GET /history and DELETE /history — chat continuity.

SECURITY FIX: `session_id` is now REQUIRED. It was optional, with no
authentication, so calling GET /history bare returned every user's chat
history — including free-text descriptions of their skin, which is
health-adjacent personal data. That was the most serious defect in the
original codebase and it is fixed here rather than noted as future work.

In production the session would additionally be bound to a signed token so a
guessed ID doesn't work either, and rows would carry a TTL.
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_rag_service
from app.schemas.chat import HistoryResponse
from app.services.rag_service import RAGService

router = APIRouter()


@router.get("/history", response_model=HistoryResponse, summary="Get chat history")
async def get_history(
    session_id: str = Query(..., min_length=8, description="Required — scopes to one conversation"),
    limit: int = Query(50, ge=1, le=200),
    service: RAGService = Depends(get_rag_service),
) -> HistoryResponse:
    """Retrieve one session's chat history."""
    return await service.get_history(session_id=session_id, limit=limit)


@router.delete("/history", summary="Clear chat history")
async def clear_history(
    session_id: str = Query(..., min_length=8),
    service: RAGService = Depends(get_rag_service),
) -> dict[str, int | str]:
    """Delete a session's chat history for real, not just hide it."""
    deleted = await service.clear_history(session_id)
    return {"session_id": session_id, "deleted": deleted}
