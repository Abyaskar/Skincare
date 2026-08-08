# AI Beauty Recommendation Engine

Production-ready backend for personalized skincare product recommendations, built for the **Orbo AI Generative AI Internship**.

Uses **Python 3.12**, **FastAPI**, **MongoDB (Motor)**, **FAISS**, **Sentence Transformers**, and **RAG** with **Gemini/OpenAI**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI (Swagger UI)                     │
│  /recommend  /chat  /search  /products  /feedback  /history │
└──────────────────────────┬──────────────────────────────────┘
                           │ Dependency Injection (deps.py)
┌──────────────────────────▼──────────────────────────────────┐
│                        Services Layer                        │
│  RecommendationService │ SearchService │ RAGService          │
│  PreprocessingService │ EmbeddingService │ VectorStore       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     Repository Layer                         │
│  ProductRepository │ FeedbackRepository │ HistoryRepository  │
└──────────────────────────┬──────────────────────────────────┘
                           │ async/await (Motor)
┌──────────────────────────▼──────────────────────────────────┐
│              MongoDB                    FAISS Index          │
│         (products, feedback,         (vector embeddings)    │
│          chat_history)                                       │
└─────────────────────────────────────────────────────────────┘
```

### Clean Architecture Layers

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **API** | HTTP routing, request validation | `app/api/` |
| **Schemas** | Pydantic DTOs (API contract) | `app/schemas/` |
| **Services** | Business logic, ML/RAG orchestration | `app/services/` |
| **Repositories** | Async MongoDB data access | `app/repositories/` |
| **Models** | Internal document models | `app/models/` |
| **Core** | Config, logging, exceptions, DB | `app/core/` |
| **Utils** | Text/price parsing helpers | `app/utils/` |

### Key Design Decisions

1. **Repository pattern** — Services never touch MongoDB directly; repositories are injected via FastAPI `Depends()`, enabling easy mocking in tests.

2. **FAISS + MongoDB hybrid storage** — Product metadata lives in MongoDB; dense embeddings live in a FAISS `IndexFlatIP` (cosine similarity via L2-normalized inner product). An ID map links FAISS row indices to MongoDB ObjectIds.

3. **Singleton embedding model** — `SentenceTransformer` is loaded once per process (`@lru_cache`) to avoid repeated 400MB+ model loads.

4. **Async-first** — All MongoDB I/O uses Motor. CPU-bound embedding inference runs in `run_in_executor` to avoid blocking the event loop.

5. **Graceful LLM fallback** — RAG chat works without an API key (returns retrieval-only results). Configure `GEMINI_API_KEY` or `OPENAI_API_KEY` for full generative answers.

6. **Heuristic enrichment** — The raw dataset lacks brand/skin-type columns. The preprocessing pipeline extracts brands from product names and infers skin-type compatibility from ingredient keywords.

---

## Project Structure

```
.
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── api/
│   │   ├── deps.py             # Dependency injection container
│   │   └── v1/
│   │       ├── router.py       # Route aggregation
│   │       └── endpoints/      # recommend, chat, search, products, feedback, history
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (.env)
│   │   ├── database.py         # Motor connection manager
│   │   ├── exceptions.py       # Domain exception hierarchy
│   │   └── logging.py          # Structured logging
│   ├── models/                 # MongoDB document models
│   ├── schemas/                # API request/response schemas
│   ├── repositories/           # Async data access
│   ├── services/               # Business logic
│   └── utils/                  # Text/price utilities
├── scripts/
│   └── ingest_data.py          # Dataset preprocessing + ingestion
├── data/                       # FAISS index (generated)
├── skincare_products_clean.csv # Dataset
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- MongoDB running locally (or MongoDB Atlas URI)
- (Optional) Gemini or OpenAI API key for RAG chat

### Setup

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
# Edit .env with your MongoDB URI and API keys

# 4. Ingest dataset (clean → MongoDB → embeddings → FAISS)
python scripts/ingest_data.py

# 5. Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/recommend` | Content-based, semantic, or hybrid recommendations |
| `POST` | `/chat` | RAG-powered natural language Q&A |
| `POST` | `/search` | Semantic product search |
| `POST` | `/feedback` | Submit user feedback on recommendations |
| `GET` | `/products` | Paginated product catalog |
| `GET` | `/product/{id}` | Single product detail |
| `GET` | `/history` | Chat conversation history |
| `GET` | `/health` | Health check |

### Example: Hybrid Recommendation

```json
POST /recommend
{
  "query": "hydrating moisturiser for dry sensitive skin",
  "strategy": "hybrid",
  "top_k": 5,
  "filters": {
    "max_price": 20,
    "skin_type": "dry",
    "ingredients_include": ["hyaluronic acid"],
    "brands": ["CeraVe", "The Ordinary"]
  }
}
```

### Example: RAG Chat

```json
POST /chat
{
  "message": "I have oily acne-prone skin and a £15 budget. What moisturiser should I use?",
  "top_k": 5
}
```

---

## Preprocessing Pipeline

The ingestion script (`scripts/ingest_data.py`) performs:

1. **Load CSV** — reads `skincare_products_clean.csv`
2. **Clean missing values** — drops rows without product name/type
3. **Remove duplicates** — deduplicates by normalized product name
4. **Normalize text** — lowercase, strip whitespace, parse ingredient lists
5. **Enrich metadata** — extract brand, parse GBP prices, infer skin types
6. **Build search text** — concatenated field for embedding
7. **Store in MongoDB** — async bulk insert via Motor
8. **Generate embeddings** — `all-MiniLM-L6-v2` (384-dim)
9. **Build FAISS index** — persisted to `data/faiss_index.bin`

---

## Recommendation Strategies

| Strategy | How it works | Requires |
|----------|-------------|----------|
| **content** | Jaccard similarity on ingredients + type/brand bonus | `product_id` |
| **semantic** | FAISS cosine similarity on query embedding | `query` |
| **hybrid** | Weighted fusion (default 60% semantic + 40% content) | `query` (+ optional `product_id`) |

### Filters (all strategies)

- **Budget**: `min_price`, `max_price` (GBP)
- **Skin type**: `oily`, `dry`, `combination`, `sensitive`, `normal`
- **Ingredients**: include/exclude lists (case-insensitive)
- **Brand**: multi-brand filter
- **Product type**: category filter (Moisturiser, Cleanser, etc.)

---

## RAG Pipeline

```
User Question → Embed → FAISS top-k retrieval → Build context prompt → LLM → Answer
                                              ↓
                                    Save to chat_history
```

The LLM receives structured product context (name, brand, price, ingredients, skin types) and generates explainable recommendations citing specific products.

---

## Scalability Improvements

| Area | Current | Production Scale |
|------|---------|-----------------|
| Vector search | FAISS in-process | Pinecone, Weaviate, or MongoDB Atlas Vector Search |
| Embeddings | Local Sentence Transformers | Batch API (OpenAI, Cohere) or dedicated GPU service |
| MongoDB | Single instance | Replica set + sharding by product category |
| API | Single Uvicorn worker | Gunicorn + multiple workers behind load balancer |
| Caching | None | Redis for hot queries and embedding cache |
| Ingestion | Synchronous script | Celery/Arq background job with progress tracking |
| LLM | Direct API calls | Queue-based with rate limiting and retry |

---

## Future Enhancements

- [ ] Collaborative filtering from user feedback signals
- [ ] Personalization via user skin profile persistence
- [ ] Ingredient conflict / allergen detection
- [ ] A/B testing framework for recommendation strategies
- [ ] Prometheus metrics + OpenTelemetry tracing
- [ ] Admin endpoint for re-ingestion and index rebuild
- [ ] Multi-language support for product descriptions
- [ ] Image-based product similarity (CLIP embeddings)
- [ ] Fine-tuned reranker for hybrid results
- [ ] Rate limiting and API key authentication

---

## Environment Variables

See `.env.example` for all configuration options. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | — |
| `EMBEDDING_MODEL_NAME` | Sentence Transformers model | `all-MiniLM-L6-v2` |
| `HYBRID_SEMANTIC_WEIGHT` | Hybrid semantic weight | `0.6` |

---

## License

Built for educational purposes as part of the Orbo AI Generative AI Internship project.
