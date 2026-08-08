"""POST /recommend — multi-strategy product recommendations."""

from fastapi import APIRouter, Depends

from app.api.deps import get_recommendation_service
from app.schemas.recommendation import RecommendRequest, RecommendResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.post("", response_model=RecommendResponse, summary="Get product recommendations")
async def recommend(
    request: RecommendRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendResponse:
    """
    Generate product recommendations using one of three strategies:

    - **content**: Similar products based on ingredient overlap (requires `product_id`)
    - **semantic**: Vector similarity search on natural language query
    - **hybrid**: Weighted combination of semantic + content-based (default)
    """
    return await service.recommend(request)
