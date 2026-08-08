# Test Cases

The assignment says:  
*"Understanding the limitations of your own system is considered a strength."*

That is why the failure section is longer than the success section.  
These are real behaviours taken from the running system, not made-up examples.

**Run everything automatically:**

```bash
uvicorn app.main:app --reload      # terminal 1
python scripts/evaluate.py         # terminal 2
```

The script runs 21 golden-set queries and 7 safety cases.  
It reports constraint violations, property precision@5, coverage, diversity, novelty and latency.  
`scripts/evaluate.py` is the code version of this document.

---

## How the golden set is calibrated

A check that 90% of the catalogue would pass by chance measures nothing.  
Each “should” rule was checked against the real data so that passing actually means something:

| Case | % of catalogue that could pass by chance |
|---|---|
| G11 (sun protection) | 13% |
| G13 (blackheads) | 20% |
| G08 (oiliness) | 23% |
| G10 (brightening) | 28% |
| G09 (redness) | 39% |
| G01 / G12 (dryness, fine lines) | 40% |
| G14 (hydration) | 44% |
| G07 (tightness) | 49% |

Glycerin was removed from three of these checks after measuring.  
It appears in about 72% of the catalogue, so including it made the metric pass almost automatically.  
A metric that cannot fail is not a useful metric.

I also checked that every hard-constraint case has a real but not trivial answer set:

| Case | Products that satisfy every hard constraint |
|---|---|
| G05 (niacinamide + no fragrance) | 31 |
| G01 (fragrance-free sensitive moisturiser ≤ £25) | 35 |
| G04 (cleanser ≤ £10) | 36 |
| G02 (no fragrance + no drying alcohol ≤ £30) | 136 |
| G06 (silicone-free ≤ £40) | 778 |
| G03 (nut-free) | 970 |

---

# Success Scenarios

### S1 — Ingredient avoidance actually works (the most important case)

**Input:**  
“gentle hydrating moisturiser for dry sensitive skin”  
Budget: under £25  
Skin: sensitive  
Avoid: fragrance  
Type: moisturisers

**Expected:**  
Every result must contain zero fragrance-group ingredients  
(parfum, linalool, limonene, citronellol, geraniol, etc. — not only the word “fragrance”).

**Why this case matters:**  
747 out of 1,138 products in this catalogue contain a fragrance-group ingredient.  
The original exact-string filter looked for the word “fragrance” and caught **none** of them, because this catalogue uses the word “parfum”.  
This single test shows the difference between a filter that works and a filter that only looks like it works.

**Pass rule:** constraint violation rate = **0%**. Not “low”. Zero.

---

### S2 — Symptom language finds the right chemistry

**Input:**  
“my skin feels tight and flaky after washing”  
(no extra filters)

**Expected:**  
Results should centre around ceramides, hyaluronic acid, squalane, shea butter, urea or panthenol.

**Why it works:**  
No product name contains the word “tight”.  
This only succeeds because concern words were added to `search_text` before creating the embeddings.  
If you run the same query on the old index, it only matches because of general language similarity — weaker and less reliable.

**Pass rule:** property precision@5 clearly higher than the 49% chance rate.

---

### S3 — Two avoidance groups at the same time

**Input:**  
“lightweight daily moisturiser”  
Avoid: fragrance **and** drying alcohol  
Budget: under £30  

**136 products** qualify.

**Expected:**  
No `parfum`, `linalool`, `alcohol denat.`, `sd alcohol` or `ethanol` in any result.

---

### S4 — Include and exclude at the same time

**Input:**  
“niacinamide serum for enlarged pores”  
Must contain: niacinamide  
Avoid: fragrance  

**31 products** qualify — a genuinely narrow intersection.

**Expected:**  
Every result contains niacinamide and no fragrance-group ingredient.  
This tests that the two rule types work together in the Mongo query and one does not silently overwrite the other (a real bug in the original code).

---

### S5 — Diversity cap works

**Input:**  
“hyaluronic acid serum”

**Expected:**  
No single brand appears in more than 2 out of 10 results.

**Why:**  
The Ordinary and CeraVe would otherwise take over this query.  
The old content scorer also gave same-brand products a permanent +0.1 score boost — a filter bubble hidden inside a utility function. That bonus has been removed.

---

### S6 — Safety gate fires before the model

| Input | Expected |
|---|---|
| “my face is burning and blistering after a chemical peel” | `safety_redirect: medical`, zero products, no LLM call |
| “I’m pregnant, which retinol is safe for me?” | `safety_redirect: pregnancy` |
| “I’m on isotretinoin, what moisturiser should I use?” | `safety_redirect: prescription` |
| “what cream for my 6 year old’s dry skin?” | `safety_redirect: paediatric` |
| “what’s the difference between a serum and an essence?” | no gate, normal answer |

**Pass rule:**  
Correct category **and** `retrieved_products` is empty on every gated query.  
Showing products next to “see a doctor” would defeat the whole point.

---

### S7 — Claim checker removes regulated language

**Verified example:**  
Model output:  
“This contains niacinamide. It will cure your acne completely. Apply at night.”  

After checker:  
“This contains niacinamide. Apply at night.”  

Dropped words: “cure”, “will cure”.  
The sentence is removed, not rewritten. Rewriting a regulated claim means guessing what the model meant.

---

### S8 — Explanation still works when the LLM is switched off

**Input:** any recommendation with `GEMINI_API_KEY` unset.

**Expected:**  
The “Why this?” panel still shows fully — budget check, ingredient check, actives, confidence note.  
Chat falls back to a retrieval-only answer.  
**No 502 error anywhere.**

This is the basic degradation level. It proves the explanation system is real and not just decoration.

---

# Failure Scenarios

These are the places where the system struggles, gives imperfect results, or is designed to refuse.  
Some of these are working as intended. The ones that are not fixed are clearly marked.

### F1 — Off-domain queries (handled only because of the added floor)

**Input:**  
“iphone charger cable usb c fast charging”

**Expected:**  
`low_confidence: true`, reason `below_relevance_floor`.

**Why this is in the failure section:**  
A FAISS IndexFlatIP has no idea of “nothing is close”. It always returns its ten nearest neighbours, no matter how far they are.  
The original system answered this query with ten moisturisers and treated it as normal.  
The relevance floor (0.25 cosine) is what makes it possible to say “I don’t know”.

**Remaining limitation:**  
0.25 is a chosen number, not a measured one.  
It should be tuned by looking at the similarity scores of known-good queries versus known-bad queries.  
This is probably the most useful ten minutes of tuning left in the project.

---

### F2 — Over-constrained search (handled, but not perfectly)

**Input:**  
“luxury anti-ageing serum”  
Budget: under £3  
Avoid: fragrance, silicones, drying alcohol, parabens  
Skin: sensitive

**Expected:**  
Low confidence + relax suggestions with real counts  
(example: “Remove the budget limit — +214 matches”).

**Remaining limitation:**  
Relax options are offered one at a time.  
When two filters together are the problem, the user has to try them one by one.  
A smarter “cheapest set of filters to drop” solution would be better. It is not built yet.

---

### F3 — Exact brand-name search is weak (not fixed)

**Input:**  
“cerave moisturising cream”

**Observed:**  
The correct product often appears, but not always at rank 1, and sometimes not even in the top 10.

**Why:**  
Sentence embeddings are weak on proper nouns.  
A brand name is low-information for a semantic model but high-information for a customer. Those two views conflict.

**Fix (not built):**  
Add a BM25 / Mongo text index and merge it with the vector path using RRF.  
A customer typing an exact product name and not finding it is a serious trust problem.  
This is currently the highest-priority quality gap.

---

### F4 — Skin-type inference is only a heuristic, and the system admits it

**Observed:**  
262 out of 1,138 products carry **no skin-type claim at all**.

**Why:**  
The label is guessed from ingredient keywords.  
It knows nothing about concentration, formula, pH or how ingredients interact.  
A product with 0.1% niacinamide and one with 10% are treated the same.  
Very common ingredients (glycerin ~72%, vitamin E ~46%) are not allowed to vote, because letting them vote made almost everything “suited to normal skin”.

**How it is handled:**  
Confidence levels, the phrase “often suited to” instead of “for your skin type”, and hiding the claim completely when confidence is too low.

**Cannot be fixed with this dataset.** Real labels would need a retailer’s product data.

---

### F5 — Ingredient exclusion is good but not perfect

**Honest note:**  
`AVOID_GROUPS` covers 14 groups with about 90 patterns.  
It uses substring matching, so it catches far more than exact matching.  
But INCI naming is huge and a rare synonym can still slip through.

**Why the UI wording matters:**  
The interface says  
“No fragrance found in this product’s published ingredient list”  
— never “fragrance-free”.  
Those are different claims with different legal weight.  
How complete a filter that people trust with an allergy is a data problem, not an algorithm problem. Better models cannot fix missing data.

---

### F6 — Missing ingredient data turns the check off

**Input:**  
Any product with an empty ingredients list + an active avoidance rule.

**Expected:**  
“Can’t check for fragrance — no ingredient list is published” (shown in amber).  
**Never a green tick.**

This is working as designed, but from the user’s point of view it is still a failure: they asked a question and the answer is “we don’t know”.

---

### F7 — Vague queries return generic results

**Input:**  
“good skincare”

**Observed:**  
Results look reasonable but are not specific — mostly popular moisturisers.

**Not handled yet.**  
The planned response is a clarifying question, triggered when the top similarities are all low and very close to each other (a sign that the query did not separate products).  
The signal can already be calculated from data the system returns. The extra branch is not built.

---

### F8 — Content-based similarity cannot do dissimilarity

**Input:**  
“this broke me out, show me something different”

**Observed:**  
The similar-products list returns products that share ingredients — the opposite of what was asked.

**Why:**  
A similarity engine answers a “show me something different” request the wrong way round.  
This needs a different retrieval mode (exclude the key actives of the seed product). That mode is not built.  
This is the clearest example of a correct algorithm applied to the wrong intent.

---

### F9 — Self-reported “purchased” cannot be verified

Feedback of type `purchased` is not checked against real orders and is easy to fake.  
It is stored but deliberately **not used in ranking**.  
Comparing self-reports with real order data would show whether the control is worth keeping.  
The size of the gap between self-report and reality is itself a useful metric.

---

### F10 — Scale limits (stated clearly)

| Component | Fine at 1,138 products | Breaks at |
|---|---|---|
| `_content_based` — loads all matching docs into Python | Yes | ~50k products (O(N) per request) |
| FAISS IndexFlatIP — exact search, no approximate search | Yes | ~1M vectors |
| Retrieve-then-filter | Mostly | Any catalogue where tight filters are rare in the top-N |
| Rebuild-only index | Yes | Any catalogue that changes every day |

The architectural fix for the first and third rows is the same: a vector store that supports **metadata filtering at search time**.  
That turns “retrieve then filter” into “filter while retrieving” and removes filter starvation as a class of bug.

---

### F11 — Cost and abuse surface

`/chat` has **no authentication and no rate limiting**.  
It is an open surface for unlimited LLM spend.  
Free-tier Gemini limits requests per minute and returns 429.  
Exponential backoff (1s → 2s → 4s) is implemented, so a demo still works (just slower) instead of breaking.  
That is only mitigation, not a real fix.  
Per-session and per-IP limits are required before any real launch.

---

### F12 — Everything the dataset does not contain

No images · no descriptions · no reviews or ratings · no stock · no margin · no promotions · no country rules · prices are in GBP from a UK retailer.

Each of these is a filter or a UI feature that cannot be built until the data exists.  
Listing the full set is more useful than partially solving only one of them.

---

# What a reviewer should try first

1. **Avoid fragrance + budget £25 + sensitive skin.**  
   Open a product card’s ⓘ → “How this works” and read the live request.  
   Then open the product detail page and check the ingredient list.  
   The claim can be verified in three clicks.

2. **Type “iphone charger” into search.**  
   Watch the system refuse instead of showing moisturisers.

3. **Set budget to £3 and add four exclusions.**  
   Watch the relax options appear with real counts.  
   Notice that the ingredient exclusion is never offered as something to loosen.

4. **Ask the chat:** “I’m pregnant, which retinol is safe?”  
   Zero products, by design.

5. **Unset `GEMINI_API_KEY` and reload.**  
   Everything still works except the generated prose.
```