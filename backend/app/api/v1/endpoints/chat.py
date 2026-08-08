"""POST /chat — RAG-powered beauty Q&A."""

from fastapi import APIRouter, Depends

from app.api.deps import get_rag_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import RAGService

router = APIRouter()


@router.post("", response_model=ChatResponse, summary="Ask a beauty question (RAG)")
async def chat(
    request: ChatRequest,
    service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    """
    Natural-language skincare Q&A with retrieval-augmented generation.

    Retrieves relevant products via vector search, then generates an
    explainable answer using Gemini or OpenAI.
    """
    return await service.chat(request)
