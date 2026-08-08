"""
Embedding service using Sentence Transformers.

Loads the model once (singleton) and exposes sync encode methods.
Encoding runs in a thread pool from async callers to avoid blocking
the event loop during CPU-bound inference.
"""

import asyncio
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load embedding model once per process."""
    logger.info("Loading embedding model: %s", settings.embedding_model_name)
    return SentenceTransformer(settings.embedding_model_name)


class EmbeddingService:
    """Generates dense vector embeddings for text."""

    def __init__(self) -> None:
        self._model = _load_model()
        self.dimension = settings.embedding_dimension

    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Synchronous batch encoding — call via encode_async from routes."""
        if not texts:
            return np.array([]).reshape(0, self.dimension)
        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return np.asarray(embeddings, dtype=np.float32)
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise EmbeddingError("Failed to generate embeddings", details={"error": str(exc)}) from exc

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    async def encode_async(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Non-blocking wrapper for FastAPI async handlers."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.encode(texts, batch_size=batch_size)
        )

    async def encode_single_async(self, text: str) -> np.ndarray:
        result = await self.encode_async([text])
        return result[0]
