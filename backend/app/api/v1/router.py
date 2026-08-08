"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import chat, feedback, history, products, recommend, search

api_router = APIRouter()

api_router.include_router(recommend.router, prefix="/recommend", tags=["Recommendations"])
api_router.include_router(chat.router, prefix="/chat", tags=["RAG Chat"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(products.product_detail_router, prefix="/product", tags=["Products"])
api_router.include_router(history.router, tags=["History"])
