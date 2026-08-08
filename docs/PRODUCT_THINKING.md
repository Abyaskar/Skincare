# Product Thinking — The Ten Questions

This document explains the main product decisions behind Formulary.  
Every answer has three parts:

1. Business reason  
2. Technical decision that follows from it  
3. What is actually built in this project vs what is still a plan  

The third part is the most important. Saying something works when the code does not have it is worse than honestly saying “this is not done yet”.

---

# 0. How this project maps to the assignment

Read this first. It tells you what is already done and what is still missing.

| Required deliverable | Status | Where |
|---|---|---|
| 1. Working recommendation system | **Done** | `backend/` — 3 strategies, 1,138 products, FAISS + MongoDB |
| 2. Testing interface (mandatory) | **Done, and more than asked** | `frontend/` — full guided flow (brief only asked for simple UI) |
| 3. Documentation | **Partial** | README covers setup. Still needed: problem statement, architecture, dataset reason, assumptions |
| 4. Test cases — success **and failure** | **Missing** | See `TEST_CASES.md` and `scripts/evaluate.py` |
| 5. Evaluation metrics | **Missing as a finished report** | Metrics are designed but not fully run yet. See Q3 |
| Bonus — copy an existing product + comparison | **Not done on purpose** | Decision explained below |

### The three gaps (in order of importance)

**Gap 1 — Evaluation is mandatory and still incomplete.**  
The brief lists precision, recall, NDCG, MAP, diversity, coverage, novelty, latency.  
I have no relevance labels, so normal precision and NDCG cannot be calculated the usual way.  
The brief already says: *“If standard metrics are not applicable, clearly justify the evaluation methodology you choose.”*  
That sentence is an invitation. Using it properly is better than inventing fake scores.

What I actually use in `backend/scripts/evaluate.py`:

- A small golden set of ~20 queries with expected **properties**, not expected products.  
  Example: “fragrance-free moisturiser for dry skin under £25” → every result must have zero fragrance ingredients, be a moisturiser, and cost ≤ £25.
- **Constraint violation rate** — the most important metric here. Target is **zero**. A system that is 95% accurate but shows an allergen 5% of the time cannot be shipped.
- Catalogue coverage, diversity, novelty, latency, and low-confidence rate — all can be calculated today without labels.
- Precision@5 on a small hand-labelled set, with the sample size clearly written so nobody thinks it is a big benchmark.

**Gap 2 — Failure cases are scored.**  
The brief says understanding your own limitations is a strength.  
This project was built around failure cases from the start (low-confidence screen, relevance floor, safety gate, filter attrition). That is intentional.

**Gap 3 — The bonus challenge, and why I did not clone Nykaa.**

The bonus asks to make the UI look like Nykaa or Sephora. I deliberately did not.  
This is a real decision with a trade-off, so I should be able to defend it.

- **Case for cloning:** it is asked, low risk, shows you can follow a reference.
- **Case for what I built:** the brief values originality and product thinking. A Nykaa-looking UI with different backend only shows CSS skill. A design that solves a real data problem (no product photos) shows product thinking.

**My choice:** keep the original UI and still write the comparison.  
That way I answer the real purpose of the bonus (benchmark against industry) without just copying the look.  
The comparison is in `docs/BENCHMARK_NYKAA.md`.

If there is extra time at the end, the cheapest extra is a theme toggle (same components, different colour tokens). The design system already uses tokens, so it would only be a stylesheet change.

---

# The ten questions

---

## Q1. Who exactly is my customer?

### Business answer

Naming a big segment is less useful than naming the **moment**.  
A 19-year-old with breakouts and a 45-year-old with a fragrance allergy are in the same situation: standing in front of a thousand products, unable to read the ingredient list, about to guess.

I still need a primary customer.  
**Primary customer = the shopper who has a hard constraint** (cannot use a certain ingredient, or has a fixed budget, or both).

Why this group first?

- They are badly served today. Almost no beauty site lets you filter out fragrance. People currently read long ingredient lists by hand.
- Their constraint makes the system easy to get right and easy to fail visibly — that pressure forces better design.
- They buy based on trust, not only on discounts.
- Solving for them automatically makes the product better for everyone else. The opposite is not true.

Who is **not** the customer:

- Dermatologists and consultants (different product, different liability).
- Teenagers as a target segment. Under-18 users need age checks and extra care that this project does not provide. The safety gate simply routes them out.

### Technical answer

This choice shows up in the code:

- Ingredient exclusion is the strongest filter. It runs in MongoDB **and** again in Python.
- The intake form asks about avoidance early (step 3 of 4).
- Product cards highlight matched constraints — that is the main visual idea.
- No customer segmentation model. Preferences are stated by the user, not guessed by the system.

### In this build

Fully implemented.  
Real result: **747 of 1,138 products** contain a fragrance-group ingredient. The old exact-string filter caught **none** of them.

### How I would say it in an interview

> “I designed for the shopper who has a hard constraint — allergy or firm budget — rather than for the casual browser. Nobody serves them well today. Building for them forces the system to be honest. If the system has to be correct about an allergen, the model cannot decide anything important. Solving for the constrained customer makes the product better for everyone else. The reverse does not work.”

---

## Q2. What problem am I solving?

### Business answer

There are several ways to describe the problem. They sit on a chain:

```
Cannot read ingredients → cannot choose with confidence → wrong purchase or no purchase
```

The **root problem is a literacy gap**, not a discovery gap.  
Discovery tools assume the customer already knows what they want.  
Here the customer knows their **symptom** and the catalogue is organised by **chemistry**. There is no translation between the two.

Conversion and returns are **results** of the gap, not the problem itself.  
If you call the problem “increase conversion”, the cheap fix is urgency and discounts. That works for a short time and then damages trust.  
If you call it “close the literacy gap”, the fix is explanation — which improves conversion **and** reduces returns.

What this project actually attacks (in order):

1. Translate symptom language into product chemistry  
2. Enforce constraints the customer cannot check themselves  
3. Make the reasoning checkable  
4. Conversion and returns follow later

### Technical answer

| Problem | How it is solved | File |
|---|---|---|
| Symptom → chemistry | Concern words added to `search_text` before embedding | `preprocessing_service.py`, `ingredient_intel.py` |
| Constraint enforcement | Mongo filters + Python re-check | `recommendation_service.py` |
| Checkable reasoning | Reasons built from rules, not from the LLM | `explain.py` |
| Not guessing | Relevance floor + low-confidence state | `config.relevance_floor` |

The original `search_text` was only name + type + brand + ingredients.  
When a user typed “soothing for redness”, the match happened only because the embedding model already knew “aloe” and “centella” are near “soothing”. The data itself had **no customer language**.  
Adding concern vocabulary made the translation real.

### In this build

Implemented. It required a full re-ingest because the embeddings changed.

### How I would say it in an interview

> “The problem is not discovery. It is literacy. Customers talk in symptoms — ‘tight after washing’, ‘shiny by lunch’. The catalogue talks in chemistry. There is no bridge. Conversion and returns are consequences of that gap. If you treat it only as a conversion problem, the cheap fix is discounts. If you treat it as a literacy problem, the fix is explanation, which helps both.”

---

## Q3. How do I measure success?

### Business answer

Some metrics are more trustworthy than others.

| Metric | What it really tells you | Trust level | Role |
|---|---|---|---|
| CTR | The card looked nice | Low | Only for diagnosis |
| Recommendation acceptance | Ranking looked reasonable | Medium | Main optimisation target |
| Recommendation → cart | Customer committed | Medium-high | Main business metric |
| Conversion | They paid | High | Final outcome |
| AOV | Basket size | High (easy to game) | Guardrail only |
| **Repeat purchase** | **It worked on their skin** | **Highest** | **North star** |

North star = repeat purchase (and purchases that are not returned after 30 days).  
Beauty is a replenishment business. A customer who buys again has tested the product on their own face.

I would **not** optimise CTR. CTR only measures if the card looked tempting. In skincare the gap between “tempting” and “suitable” can actually hurt someone.

Two extra metrics I care about:

- **Constraint violation rate** — target **zero**. This decides if a real retailer will use the system.
- **Low-confidence rate** — should stay non-zero and stable. Driving it to zero means the honesty check is broken.

### Technical answer

**Offline metrics (can be calculated today):**

| Metric | Can we calculate it now? |
|---|---|
| Constraint violation rate | Yes |
| Catalogue coverage | Yes |
| Intra-list diversity | Yes |
| Novelty | Yes |
| Latency p50 / p95 | Yes |
| Low-confidence rate | Yes |
| Precision@5 on small golden set | Yes (small sample) |
| NDCG / MAP / Recall | **No** — needs graded labels I do not have |

**Online metrics (need real traffic):** acceptance rate, cart rate, conversion, repeat purchase, return rate.

Every online metric needs `request_id` linking impression → click → feedback → cart. Without it, acceptance rate cannot be measured. The original backend did not have this.

### In this build

`request_id` and reason codes are implemented end-to-end.  
Offline metrics are in `scripts/evaluate.py`.  
Online events are named in the frontend but **not yet sent to any store**. I will say that clearly.

### How I would say it in an interview

> “The north star is repeat purchase, because beauty is a replenishment category. Everything else is a leading indicator. I would not optimise CTR — it only measures if the card looked appealing. In skincare the gap between tempting and suitable can hurt someone. The two metrics I add are constraint violation rate (target zero) and low-confidence rate (should stay non-zero).”

---

## Q4. What information should I collect *before* recommending?

### Business answer

Every question costs customers. Ask only the questions that change the answer the most.

**Must collect (hard constraints)**

| Field | Why | Required? |
|---|---|---|
| Concern / goal | Only real intent signal | One signal is mandatory |
| Ingredient avoidance | Highest value field in the whole flow | Optional but strongly prompted |
| Budget | Hard filter, clear, easy to answer | Optional |
| Product type | Stops showing ten moisturisers when user wants a cleanser | Optional |

**Collect but treat as soft**

- Skin type — people often mis-report it. Use only for ranking, never as a hard filter.
- Brand preference — real but can create filter bubbles.

**Never collect as a form field — only detect and route out**

- Pregnancy, medical conditions, prescription use, children’s use.  
  Asking “are you pregnant?” is invasive and creates sensitive data you then have to protect.  
  Instead: detect the words in free text and immediately say “please check with a doctor or pharmacist”. No products are shown.

**Not collected yet (value does not justify cost right now)**

- Location (useful later for currency and stock)
- Climate (useful but second-order; should be asked, not inferred from IP)

### Technical answer

- Intake has four steps. Everything after the first can be skipped.
- Only one `/recommend` call at the end (not one call per step).
- Filter options come from live catalogue (`GET /products/facets`) so the UI never offers a filter that returns nothing.
- Safety gate is a simple keyword check in `safety.py`, tuned for high recall.

### In this build

All four steps are implemented. Safety gate covers medical, prescription, pregnancy and paediatric cases. Location and climate are deliberately not collected.

### How I would say it in an interview

> “Every question costs customers, so I asked the fewest that change the answer most: concern, avoidance, budget, product type. The interesting one is pregnancy. It is a real safety question but a terrible form field. So I never ask it and never store it. I only detect the words and route the user to a professional before the model is called.”

---

## Q5. When should I *not* recommend?

### Business answer

Being able to say “I don’t know” is what makes the confident answers believable. A system that always returns something is not confident — it is just silent.

Six situations and three different responses:

| Situation | Response | Why |
|---|---|---|
| Medical / pregnancy / paediatric | Refuse completely. No products. Route to professional | Recommending a cosmetic for a medical problem is the worst outcome |
| Below relevance floor | “I am not confident” + suggest rephrasing | Nearest-neighbour search always returns something, even if far away |
| Fewer than 3 results after filters | Name the constraint + one-tap relax with count | Turns a dead end into a choice |
| Missing ingredient data | Never show a green tick for avoidance | False safety is worse than no feature |
| Contradictory input | Say the conflict clearly | Empty grid with no explanation is confusing |
| Budget mismatch | Filter by default, offer one clear opt-in | Hiding better products is bad; ignoring stated budget is worse |

**Hard rule:** ingredient exclusion is **never** offered as something to relax.  
Budget and skin type can be relaxed. Allergy rules cannot.

### Technical answer

```
message → safety gate (before any model) → refuse
        → embed + retrieve
        → top similarity < relevance floor → low-confidence state
        → filters + attrition tracking
        → results < 3 → low-confidence + relax options
```

Relax suggestions first count how many extra products each relaxed filter would give, so the button can say “+7 matches” before the user clicks.

### In this build

All six cases are implemented. The low-confidence screen is a designed screen, not an error page. It shows the reason, offers one-tap relax, and says “we would rather show you nothing than show you the wrong thing.”

### How I would say it in an interview

> “Being allowed to say ‘I don’t know’ is what makes the confident answers worth believing. There are six triggers with three different responses. The rule with no exception: I will offer to relax budget or skin type, never an ingredient exclusion. That is a safety rule, not a preference.”

---

## Q6. How should I explain recommendations?

### Business answer

“Product A because…” is better than just “Product A”.  
But the **kind** of “because” matters. A nice-sounding but wrong explanation is worse than no explanation.

Three levels (worst to best):

1. No explanation — customer must just trust you  
2. Plausible-sounding explanation that is not accurate — manufactures false confidence  
3. Checkable explanation — customer can verify it against the label  

Only level 3 is worth building.

**Rule:** explanations describe **matching**, never **outcomes**.

| Never say | Say instead |
|---|---|
| “Treats your acne” | “Contains salicylic acid, commonly used for breakout-prone skin” |
| “For your skin type” | “Often suited to dry skin based on its ingredients” |
| “Fragrance-free” | “No fragrance ingredients found in the published list” |
| “Will reduce wrinkles” | “Contains retinol, commonly found in anti-ageing products” |

This is also a legal point. Cosmetic claims are regulated. A generated sentence that says a product “treats” something can turn it into a medicinal claim.

### Technical answer

Explanations are built from the filters that actually ran, not written by the LLM.

```
✓ £13.00 — within your budget
✓ No fragrance found in the list
✓ Contains ceramides and hyaluronic acid
⚠ Skin-type fit is inferred, not verified
```

This gives three good properties:

- Auditable — each line can be checked against the product
- Works even if the LLM is switched off
- Safe — templates cannot invent claims

The LLM only writes one soft sentence, and that sentence still goes through a claim checker that removes words like “cures”, “treats”, “clinically proven”.

The visual explanation is also important: every product card shows the real ingredient list with matched terms highlighted.

### In this build

Fully implemented and independent of the LLM.

### How I would say it in an interview

> “Explanation is the whole product, but only if it is checkable. A nice-sounding explanation that is not true is worse than none. So the facts come from the filters that actually ran, not from the model. The panel works even if the LLM is off. And the language always describes matching, never outcomes.”

---

## Q7. What business KPI changes?

### Business answer

Every number below is a **hypothesis**. I have no production traffic and no baseline. Claiming “+20% conversion” without a baseline is just ambition.

| KPI | Expected direction | Guardrail |
|---|---|---|
| Recommendation accuracy | Up | Constraint violation rate stays at zero |
| Conversion | Up | Return rate does not rise |
| Bounce rate | Down | Intake abandonment rate |
| Time to decision | Down | Must not become “fast to the wrong product” |
| Revenue | Up | Downstream of conversion and AOV |
| Customer satisfaction | Up | Low-confidence rate not forced to zero |

**Two KPIs I expect to look “worse” and would defend:**

- Session duration goes **down** — less time to a good answer is the goal.
- Results per query goes **down** — nine explained options are better than fifty unexplained ones.

Being able to name the numbers that should go down is a stronger signal than any projected uplift.

### Technical answer

Measurement plan:

1. Week 0 — only instrument. No user-facing change. Collect baselines.
2. Weeks 1–3 — A/B test (current search vs guided flow).
3. Primary metric: recommendation-to-cart rate.
4. Guardrails: return rate, low-confidence rate, latency, price distribution.
5. Decision rule written **before** looking at data: ship only if primary improves **and** no guardrail gets worse.

### In this build

`request_id` is ready. Event emission is **not** implemented yet. Events are named in the frontend but nothing stores them.

### How I would say it in an interview

> “I would rather name the guardrails than project an uplift. The two numbers I expect to get worse are session duration (less time to a good answer is better) and results per query (nine explained options beat fifty unexplained ones).”

---

## Q8. How will feedback improve recommendations?

### Business answer

Different feedback signals have different value.

| Signal | Reliability | Role |
|---|---|---|
| Clicked | Low | Diagnostic only |
| Ignored / skipped | Low | Only useful after position debiasing |
| Liked | Low-medium | Debugging presentation |
| Disliked + reason code | **High for diagnosis** | **Bug alert, not ranking signal** |
| Saved | Medium | Mid-funnel intent |
| Purchased (self-reported) | Medium | Needs real order data to confirm |
| Kept (not returned in 30 days) | **Highest** | The real training label |

The most valuable signal today is the dislike **reason code**.  
“Contains something I avoid” is not just sentiment — it is a filter bug report from real users.

### Technical answer

Two different loops:

- **Fast loop (minutes):** thumbs and reason codes drive alerts and debugging, never ranking. A spike in “contains avoided ingredient” means a filter is broken right now.
- **Slow loop (weeks–months):** kept purchases drive ranking updates, evaluated offline, released behind A/B tests. Never retrain on same-day clicks.

`/feedback` now carries `request_id`, rank, strategy, reason code and surface. Without `request_id` none of this works.

### In this build

Schema, reason codes and filter alerts are implemented.  
The actual learning loops are designed but not running (no order data and no retraining pipeline yet).

### How I would say it in an interview

> “I rank feedback by how much it costs the customer to give. A thumbs-up is free and happens before they try the product, so I use it only for debugging. The signal I would actually train on is the kept purchase — bought and not returned after 30 days. But the highest-value thing today is the dislike reason: ‘contains something I avoid’ is a filter bug report, and it logs an alert.”

---

## Q9. How do I know a recommendation failed?

### Business answer

Most failure is silent. An explicit complaint is the rarest and latest signal.

Signals ordered by how early they appear:

| Signal | When it fires | Certainty |
|---|---|---|
| Immediate re-search | Seconds | Medium — best early signal |
| Filter relaxation | Seconds | Medium |
| No click on any result | ~30 seconds | Medium |
| Only position-1 ever clicked | Session | Medium |
| Exit from results | ~1 minute | Medium-high |
| Dislike + reason code | Instant | High |
| Return / refund | Weeks | Highest |

Two failures that look like success:

- Customer clicks and buys the wrong product (looks perfect until the return arrives).
- Zero-result rate forced to zero by always returning nearest neighbours (looks fixed, is just disguised).

### Technical answer

All signals are keyed to `request_id`.  
The API also self-reports failure: low-confidence flag, reason, and how many candidates each filter removed. This is unusual and useful.

### In this build

Self-reporting fields are implemented and visible in the UI tooltips.  
Behavioural events are named but not yet emitted.

### How I would say it in an interview

> “Most failure is silent. The signal I would watch hardest is immediate query reformulation — if someone searches again within seconds, they told you what they wanted and you did not give it. The unusual part of this system is that it self-reports failure: the response carries a low-confidence flag, the reason, and filter attrition numbers.”

---

## Q10. What data should I collect for future ML?

### Business answer

Collect only what you will actually train on. In skincare, “collect everything and figure it out later” quickly becomes health data.

**Collect (with consent and ability to delete)**

| Data | Used for |
|---|---|
| Search / query text | Understanding customer language |
| Clicked products + rank | Learning-to-rank (rank is required for position debiasing) |
| Skipped products above a click | Implicit negatives |
| Saved / wishlist | Intent without purchase |
| Feedback + reason code | Labelled relevance |
| Purchase + return outcome | The real objective (kept purchase) |
| Stated preferences from intake | Personalisation |

**Never collect or infer**

- Medical conditions from browsing
- Pregnancy or fertility status
- Age beyond a simple adult check
- Ethnicity or skin colour from product choices
- Cross-device identity without consent

**Governing rule:** store what the customer **told** you, never what you could **guess** about their body.

### Technical answer

- Session-scoped IDs by default. Account linking only on explicit opt-in.
- Rank stored with every interaction.
- Free-text chat has 90-day TTL and a real delete endpoint.
- Free text is scrubbed before any analytics.
- `/history` is now properly scoped to a session (the original version was a privacy bug).

Long-term training target: learning-to-rank model on **kept purchases**, using clicks only for candidate generation and position debiasing.

### In this build

Privacy controls are implemented.  
The collection pipeline itself is not yet built. There is no analytics store.

### How I would say it in an interview

> “The rule I use is: store what the customer told us, never what we could deduce about their body. Skincare sits next to health data. Inferring medical or pregnancy status is both a regulatory risk and the fastest way to make someone feel watched. The commercial value is in stated preferences anyway — they are more accurate and freely given. The detail people often miss is storing rank with every click: without position you cannot separate a good result from a result that was simply at the top.”

---

# Final framing and remaining work

## 30-second summary

> “I built a skincare recommender, but the interesting decisions were about where AI is **not** allowed to go. Hard constraints like allergies and budget are normal database filters that run before ranking. Vector search finds candidates. The language model only writes the explanation text. It can never add a product or override a rule. That line is what makes the system safe enough to put in front of a real retailer.”

## One-line architecture

**Rules decide the product. AI explains the choice.**

## Remaining work (ranked by priority)

| Priority | Task | Why | Effort |
|---|---|---|---|
| 1 | Finish `scripts/evaluate.py` + golden set | Mandatory and currently the biggest gap | 2–3 hours |
| 2 | Write `TEST_CASES.md` with success **and** failure cases | Mandatory; brief rewards honesty about limits | 1–2 hours |
| 3 | Full documentation (problem, architecture, dataset, assumptions) | Mandatory | ~2 hours |
| 4 | `BENCHMARK_NYKAA.md` | Covers the bonus intent without cloning | ~1 hour |
| 5 | Optional Nykaa theme toggle | Only if time left | 1–2 hours |

## Three strong points to mention

1. “Excluding ‘fragrance’ by exact string caught zero products. This catalogue calls it `parfum`. 747 of 1,138 products contain a fragrance-group ingredient, and the old filter found none of them.”

2. “The system could not say ‘I don’t have a good match’. FAISS always returns nearest neighbours, so it would answer ‘iphone charger’ with moisturisers. Being able to decline is what makes the confident answers believable.”

3. “I found a privacy bug in my own code: `/history` had no auth and an optional session ID, so it returned everyone’s chat text including free-text skin concerns. I would rather point that out myself.”

## What not to do

- Do not claim specific uplift numbers. They are only hypotheses until tested.
- Do not say “Gemini/OpenAI failover” unless the failover is actually coded (in this project it is).
- Do not imply that analytics already exist. Events are named but not stored.
- Do not oversell the skin-type inference. 262 products correctly have no skin-type claim, and that is the honest result.
```