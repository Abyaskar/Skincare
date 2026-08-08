"""
POST /feedback — closes the loop between a recommendation and its outcome.

WHY POST: each submission creates a new record with its own timestamp. Two
thumbs-down on the same product a week apart are two facts, not one overwritten
one — which is exactly what POST means and why this isn't a PUT.

WHAT CHANGED: the body now carries `request_id`, `rank`, `strategy`,
`reason_code` and `surface`. Without request_id you cannot attribute feedback to
the recommendation that produced it, which means recommendation acceptance rate
— the metric this whole product should be judged on — was not computable.

The reason codes are the real upgrade. "Not helpful" is sentiment.
"Contains something I avoid" is a filter bug report from production. Same
single tap for the customer; completely different action for the team.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_feedback_repository, get_product_repository
from app.core.logging import get_logger
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.feedback import FeedbackRequest, FeedbackResponse, ReasonCode

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=FeedbackResponse, summary="Submit feedback")
async def submit_feedback(
    request: FeedbackRequest,
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
) -> FeedbackResponse:
    """Record feedback on a recommended product."""
    # Feedback can never point at a phantom product.
    await product_repo.find_by_id(request.product_id)

    doc = await feedback_repo.create(
        {
            "product_id": request.product_id,
            "feedback_type": request.feedback_type.value,
            "request_id": request.request_id,
            "rank": request.rank,
            "strategy": request.strategy,
            "reason_code": request.reason_code.value if request.reason_code else None,
            "surface": request.surface,
            "rating": request.rating,
            "comment": request.comment,
            "session_id": request.session_id,
        }
    )

    # A cluster of these means an ingredient filter is failing in production.
    # It is the single most valuable thing feedback does today, so it gets its
    # own log line rather than being buried in an aggregate.
    if request.reason_code == ReasonCode.CONTAINS_AVOIDED:
        logger.warning(
            "FILTER ALERT: customer reports avoided ingredient present. "
            "product_id=%s request_id=%s",
            request.product_id,
            request.request_id,
        )

    return FeedbackResponse(
        id=doc.id or "",
        product_id=doc.product_id,
        feedback_type=request.feedback_type,
        request_id=request.request_id,
        reason_code=request.reason_code,
        rating=doc.rating,
        comment=doc.comment,
        created_at=doc.created_at,
    )
