"""
FastAPI dependency injection container.

Wires repositories and services with shared singletons (embedding model,
FAISS index) to avoid reloading heavy resources per request.
"""

from functools import lru_cache

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.embedding_service import EmbeddingService
from app.services.preprocessing_service import PreprocessingService
from app.services.rag_service import RAGService
from app.services.recommendation_service import RecommendationService
from app.services.search_service import SearchService
from app.services.vector_store import VectorStore


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    store = VectorStore()
    store.load()
    return store


def get_product_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> ProductRepository:
    return ProductRepository(db)


def get_feedback_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> FeedbackRepository:
    return FeedbackRepository(db)


def get_history_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> HistoryRepository:
    return HistoryRepository(db)


def get_recommendation_service(
    product_repo: ProductRepository = Depends(get_product_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> RecommendationService:
    return RecommendationService(product_repo, embedding_service, vector_store)


def get_search_service(
    product_repo: ProductRepository = Depends(get_product_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> SearchService:
    return SearchService(product_repo, embedding_service, vector_store)


def get_rag_service(
    product_repo: ProductRepository = Depends(get_product_repository),
    history_repo: HistoryRepository = Depends(get_history_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> RAGService:
    return RAGService(product_repo, history_repo, embedding_service, vector_store)


def get_preprocessing_service(
    product_repo: ProductRepository = Depends(get_product_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> PreprocessingService:
    return PreprocessingService(product_repo, embedding_service, vector_store)
