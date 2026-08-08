"""POST /search — semantic product search."""

from fastapi import APIRouter, Depends

from app.api.deps import get_search_service
from app.schemas.feedback import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.post("", response_model=SearchResponse, summary="Semantic product search")
async def search_products(
    request: SearchRequest,
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Search products by natural language query using vector similarity."""
    return await service.search(request)
