# Formulary - AI Skincare Advisor

An AI-powered skincare recommendation system built as a complete working project.

**Core idea in one line:**  
Rules decide which products are allowed. AI only explains the choice.  
The AI can never add a product, change a price, or break a safety rule.

---

## 1. Problem Statement

Finding the right skincare product is hard.  
People have different skin types, concerns, budgets, and ingredients they want to avoid.  
Most online stores just show popular products. They do not properly filter for safety or personal needs.

This project solves that problem by building an intelligent recommendation system that:

- Understands the user’s skin concerns and constraints
- Strictly filters products using rules (budget, ingredients to avoid, etc.)
- Uses AI only to explain why a product was recommended
- Clearly shows when it is not confident about a match

---

## 2. Approach & Recommendation Methodology

The system follows a clear pipeline:

1. **User inputs** their needs (skin concerns, budget, ingredients to avoid, etc.)
2. **Hard filters** are applied first (budget, excluded ingredients, safety rules)
3. **Vector search (FAISS)** finds the most relevant products from the catalogue
4. **Ranking** combines similarity scores using Reciprocal Rank Fusion (RRF)
5. **Relevance floor** removes weak matches so the system can say “I don’t have a good match”
6. **AI (LLM)** only writes the explanation text — it never decides the products

This design makes the system safe, predictable, and easy to debug.

---

## 3. Architecture

| Layer              | Technology                          | Responsibility                          |
|--------------------|-------------------------------------|-----------------------------------------|
| Frontend           | React + Vite                        | User interface and guided flow          |
| Backend API        | FastAPI                             | All business logic and endpoints        |
| Database           | MongoDB                             | Product catalogue and session data      |
| Vector Search      | FAISS                               | Semantic product retrieval              |
| LLM                | Gemini (with OpenAI failover)       | Only generates explanations             |
| Safety Layer       | Custom rules                        | Blocks medical / sensitive queries      |

**Key design rule:**  
Deterministic filters always run before ranking. The language model only writes prose.

---

## 4. Dataset

- Source: UK skincare retailer catalogue
- Original columns: name, URL, type, ingredients, price
- Size: ~1,138 products
- Brand and skin-type labels are **derived** (not original) and therefore carry confidence scores
- Prices are in GBP

New fields added during preprocessing:
- `skin_type_confidence`
- `brand_confidence`
- `concerns`
- `key_actives`
- Improved `search_text` for better vector matching

---

## 5. How to Run the Project

### Backend (requires MongoDB running locally)

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # Add your Gemini API key
python scripts/ingest_data.py     # Required — schema has changed
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

**Important:** You must re-run the ingest script. New fields were added and the FAISS index is rebuilt.

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

CORS is currently set for `localhost:5173`.  
If you run the frontend from another origin, update `cors_origins` in `app/core/config.py`.

---

## 6. App Screens

| Route          | Purpose                                              |
|----------------|------------------------------------------------------|
| `/`            | Landing page                                         |
| `/find`        | 4-step guided intake (most steps can be skipped)     |
| `/results`     | Product shortlist + low-confidence state             |
| `/product/:id` | Product detail, searchable ingredients, rules re-checked |
| `/compare`     | Side-by-side comparison of 2–3 products              |
| `/browse`      | Semantic search + paginated catalogue (no AI)        |
| `/ask`         | RAG chat (kept secondary on purpose)                 |

---

## 7. Design Decisions

**Visual direction:** Minimal luxury, clean apothecary feel.

**Signature design choice:**  
The dataset has no product photos. Instead of empty grey boxes, every product card shows the real ingredient list (INCI) in small mono font.  
Ingredients the user wants to avoid or include are highlighted.  
The card shows the evidence instead of just claiming a match.

**Colour palette:**  
- Ink `#171A18`  
- Stone `#E7E8E2`  
- Paper `#F4F5F1`  
- Pine `#24463A`  
- Clay `#A6522F` (warnings only)

**Fonts:**  
Newsreader (headings) · Archivo (body) · IBM Plex Mono (ingredients & data)

---

## 8. Important Backend Improvements

### Safety & Trust

| Change                        | Why it was needed |
|-------------------------------|-------------------|
| Relevance floor               | FAISS always returns nearest products. Without a floor, even irrelevant queries got results. |
| Synonym-aware exclusions      | “Fragrance” matched nothing because the data uses “parfum”. 747 products contain fragrance-group ingredients. |
| Session-scoped history        | Previously anyone could see all chat histories. Now session_id is required. |
| Safety gate before LLM        | Medical, pregnancy, and children’s questions get a safe reply and no products. |
| Claim checker                 | Removes regulated words like “cures”, “treats”, “clinically proven”. |

### Correctness & Quality

| Change                        | Why it was needed |
|-------------------------------|-------------------|
| Nullable price                | Failed price parsing used to return 0.0 and pass every budget filter. |
| Real LLM failover             | Gemini failure previously caused 502 errors. Now falls back to OpenAI → retrieval-only. |
| RRF ranking                   | Max-normalisation made scores look like confidence when they were not. |
| Adaptive over-fetch           | Fixed multiplier caused too few results under heavy filters. |
| Filter attrition tracking     | Explains why only a few products were returned. |
| Brand bonus removed           | Same-brand products used to get artificial score boosts. |
| Weighted Jaccard              | Common ingredients like water no longer dominate rare actives. |
| CORS fixed                    | Wildcard + credentials combination does not work in browsers. |
| request_id everywhere         | Enables proper tracking of impression → click → feedback. |
| Feedback reason codes         | Distinguishes sentiment from real filter bugs. |
| New endpoints                 | `/products/facets` and `/products/batch` for cleaner frontend. |

### Data Honesty

- Brand: 521 products matched known brands (confidence 1.0). 610 are guessed from the product name.
- Skin type: Old logic was incorrect. Near-universal ingredients (glycerin, vitamin E) no longer vote. 262 products correctly have no skin-type claim.
- Language used: “often suited to” instead of “for your skin type”.

---

## 9. The ⓘ Tooltips

Every ⓘ icon shows two layers:

1. **Simple explanation** for the end user (no jargon)
2. **“+ How this works”** — full technical details including:
   - API method and route
   - Why that method was chosen
   - Which layer produced the result
   - Real request + response with actual latency from the live call

This data comes from a live API log, not hardcoded examples.

---

## 10. Evaluation & Test Cases

### How to run evaluation

```bash
# Terminal 1
uvicorn app.main:app --reload

# Terminal 2
python scripts/evaluate.py
```

### What is measured

- Constraint violation rate (target: zero)
- Property precision@5
- Negative-control pass rate
- Catalogue coverage
- Intra-list diversity
- Novelty
- Latency (p50 and p95)

21 golden-set queries + 7 safety cases are used.

**Note:** NDCG and MAP are intentionally not reported because the dataset has no graded relevance labels. Inventing labels would only measure my own guesses.

### Documentation files

| File                          | Content                                      |
|-------------------------------|----------------------------------------------|
| `docs/PRODUCT_THINKING.md`    | Product decisions and assignment mapping     |
| `docs/TEST_CASES.md`          | Success and failure scenarios                |
| `docs/BENCHMARK_NYKAA.md`     | Comparison with Nykaa / Sephora              |
| `backend/scripts/evaluate.py` | Executable evaluation harness                |

---

## 11. Known Limitations

- No product images in the dataset (solved by design)
- Prices are in GBP (UK catalogue — not India-ready)
- No stock, promotions, margins, or country compliance rules
- No BM25 / keyword search path (exact brand search is weaker)
- No authentication or rate limiting on the chat endpoint
- Analytics events are defined in the UI but not yet stored

---

## 12. Technologies Used

- **Backend:** Python, FastAPI, MongoDB, FAISS
- **Frontend:** React, Vite
- **AI:** Google Gemini (with OpenAI failover)
- **Other:** Reciprocal Rank Fusion, custom safety rules, synonym-aware ingredient matching

---

## 13. Future Improvements

- Add product images or a better visual fallback
- Support local currency and Indian catalogue
- Add keyword / BM25 search for exact brand matching
- Add authentication and rate limiting on chat
- Store analytics events properly
- Improve mobile experience further

---

## Final Note

This project was built within the 48-hour recommendation system challenge.  
The focus was on clear thinking, safe design, honest handling of incomplete data, and making the system easy for both users and evaluators to understand.

Thank you for reviewing the project.
```
