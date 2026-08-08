#!/usr/bin/env python3
"""
Dataset ingestion script.

Usage:
    python scripts/ingest_data.py
    python scripts/ingest_data.py --csv path/to/data.csv --no-reset

Run once before starting the API server (or after dataset updates).
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import MongoDB
from app.core.logging import setup_logging, get_logger
from app.repositories.product_repository import ProductRepository
from app.services.embedding_service import EmbeddingService
from app.services.preprocessing_service import PreprocessingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


async def main(csv_path: str | None, reset: bool) -> None:
    setup_logging()
    await MongoDB.connect()
    db = MongoDB.get_database()

    product_repo = ProductRepository(db)
    embedding_service = EmbeddingService()
    vector_store = VectorStore()

    pipeline = PreprocessingService(product_repo, embedding_service, vector_store)
    summary = await pipeline.ingest(csv_path, reset=reset)

    logger.info("Ingestion complete: %s", summary)
    print("\nIngestion Summary:")
    for key, value in summary.items():
        print(f"   {key}: {value}")

    await MongoDB.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest beauty product dataset")
    parser.add_argument(
        "--csv",
        default=str(settings.dataset_path),
        help="Path to CSV dataset",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not clear existing products before insert",
    )
    args = parser.parse_args()
    asyncio.run(main(args.csv, reset=not args.no_reset))
