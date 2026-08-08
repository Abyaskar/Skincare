"""
Application configuration via Pydantic Settings.

All environment variables are loaded from `.env` at startup.
Centralizing config here keeps services decoupled from os.environ
and makes testing straightforward (override settings in fixtures).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (parent of `app/`)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the recommendation engine."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "AI Beauty Recommendation Engine"
    app_version: str = "1.0.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- MongoDB ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "beauty_recommendation"

    # --- Collections ---
    products_collection: str = "products"
    feedback_collection: str = "feedback"
    history_collection: str = "chat_history"

    # --- Embeddings & Vector Search ---
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    faiss_index_path: Path = Field(default=BASE_DIR / "data" / "faiss_index.bin")
    faiss_id_map_path: Path = Field(default=BASE_DIR / "data" / "faiss_id_map.json")

    # --- LLM (Gemini primary, OpenAI fallback) ---
    llm_provider: Literal["gemini", "openai"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Recommendation defaults ---
    default_top_k: int = 10
    rag_top_k: int = 5
    hybrid_semantic_weight: float = 0.6
    hybrid_content_weight: float = 0.4

    # --- Confidence & honesty controls ---
    # FAISS always returns its nearest neighbours however far away they are.
    # Without a floor the system can never say "I don't have a good match",
    # which is the one thing that makes the times it IS confident believable.
    relevance_floor: float = 0.25
    strong_match_threshold: float = 0.45
    min_results_before_low_confidence: int = 3

    # --- Diversity (anti filter-bubble) ---
    max_per_brand_in_results: int = 2

    # --- CORS ---
    # A wildcard with allow_credentials=True is rejected by browsers, so the
    # previous config could never have worked with a real SPA.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    # --- Dataset ---
    dataset_path: Path = Field(default=BASE_DIR / "skincare_products_clean.csv")

    # --- Logging ---
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — one parse per process."""
    return Settings()


settings = get_settings()
