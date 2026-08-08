"""
FAISS vector store for semantic similarity search.

Architecture:
- IndexFlatIP with L2-normalized embeddings → cosine similarity via inner product
- Parallel id_map stores faiss_row → mongo_product_id
- Persisted to disk for fast startup without re-embedding
"""

import json
from pathlib import Path

import faiss
import numpy as np

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """FAISS-backed vector index with MongoDB ID mapping."""

    def __init__(self) -> None:
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: list[str] = []  # faiss row index → product_id
        self.dimension = settings.embedding_dimension

    @property
    def is_loaded(self) -> bool:
        return self._index is not None and self._index.ntotal > 0

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index else 0

    def build(self, embeddings: np.ndarray, product_ids: list[str]) -> None:
        """Build a new FAISS index from embedding matrix."""
        if len(embeddings) != len(product_ids):
            raise VectorStoreError("Embeddings and product_ids length mismatch")
        if len(embeddings) == 0:
            raise VectorStoreError("Cannot build index with zero vectors")

        try:
            self._index = faiss.IndexFlatIP(self.dimension)
            vectors = np.ascontiguousarray(embeddings.astype(np.float32))
            faiss.normalize_L2(vectors)
            self._index.add(vectors)
            self._id_map = list(product_ids)
            logger.info("Built FAISS index with %d vectors", self._index.ntotal)
        except Exception as exc:
            raise VectorStoreError("Failed to build FAISS index", details={"error": str(exc)}) from exc

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Return top-k (product_id, similarity_score) pairs.

        Scores are cosine similarities in [0, 1] for normalized vectors.
        """
        if not self.is_loaded:
            raise VectorStoreError("Vector index is not loaded")

        k = min(top_k, self._index.ntotal)  # type: ignore[union-attr]
        query = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query)
        scores, indices = self._index.search(query, k)  # type: ignore[union-attr]

        results: list[tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0], strict=True):
            if idx < 0:
                continue
            results.append((self._id_map[idx], float(score)))
        return results

    def save(self, index_path: Path | None = None, id_map_path: Path | None = None) -> None:
        """Persist index and ID map to disk."""
        if not self.is_loaded:
            raise VectorStoreError("No index to save")

        idx_path = index_path or settings.faiss_index_path
        map_path = id_map_path or settings.faiss_id_map_path
        idx_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(idx_path))  # type: ignore[arg-type]
        map_path.write_text(json.dumps(self._id_map), encoding="utf-8")
        logger.info("Saved FAISS index to %s", idx_path)

    def load(self, index_path: Path | None = None, id_map_path: Path | None = None) -> bool:
        """Load index from disk. Returns False if files missing."""
        idx_path = index_path or settings.faiss_index_path
        map_path = id_map_path or settings.faiss_id_map_path

        if not idx_path.exists() or not map_path.exists():
            logger.warning("FAISS index files not found at %s", idx_path.parent)
            return False

        try:
            self._index = faiss.read_index(str(idx_path))
            self._id_map = json.loads(map_path.read_text(encoding="utf-8"))
            logger.info("Loaded FAISS index with %d vectors", self._index.ntotal)
            return True
        except Exception as exc:
            raise VectorStoreError("Failed to load FAISS index", details={"error": str(exc)}) from exc
