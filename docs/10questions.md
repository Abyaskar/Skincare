# Top 10 Product Questions — How I solved them

These are the ten questions I used to guide every major decision in Formulary.  
For each one: the business answer first, then how it shows up in the actual code.

---

## 1. Who exactly is my customer?

**Business answer**  
I designed for the shopper who has a hard constraint — cannot use a certain ingredient, or has a fixed budget, or both.  
A 19-year-old with breakouts and a 45-year-old with a fragrance allergy are in the same situation: standing in front of a thousand products, unable to read the ingredient list, about to guess.

Why this group first?
- They are badly served today. Almost no beauty site lets you properly filter out fragrance.
- Their constraint makes the system easy to get right and easy to fail visibly.
- Solving for them automatically makes the product better for everyone else. The opposite is not true.

Who is **not** the customer: dermatologists, consultants, and under-18 users (the safety gate simply routes them out).

**Technical answer**  
- Ingredient exclusion is the strongest filter. It runs in MongoDB **and** again in Python.
- The intake form asks about avoidance early (step 3 of 4).
- Product cards highlight matched constraints — that is the main visual idea.
- No customer segmentation model. Preferences are stated by the user, not guessed by the system.

---

## 2. What problem am I solving?

**Business answer**  
The root problem is a literacy gap, not a discovery gap.  
Customers talk in symptoms — “tight after washing”, “shiny by lunch”. The catalogue talks in chemistry. There is no translation between the two.

Conversion and returns are **results** of that gap, not the problem itself.  
If you call the problem “increase conversion”, the cheap fix is urgency and discounts.  
If you call it “close the literacy gap”, the fix is explanation — which improves conversion **and** reduces returns.

What this project actually attacks (in order):
1. Translate symptom language into product chemistry  
2. Enforce constraints the customer cannot check themselves  
3. Make the reasoning checkable  
4. Conversion and returns follow later

**Technical answer**  
| Problem | How it is solved | Where |
|---|---|---|
| Symptom → chemistry | Concern words added to `search_text` before embedding | preprocessing + ingredient_intel |
| Constraint enforcement | Mongo filters + Python re-check | recommendation_service |
| Checkable reasoning | Reasons built from rules, not from the LLM | explain.py |
| Not guessing | Relevance floor + low-confidence state | config.relevance_floor |

---

## 3. How do I measure success?

**Business answer**  
North star = **repeat purchase** (and purchases that are not returned after 30 days).  
Beauty is a replenishment business. A customer who buys again has tested the product on their own face.

I would **not** optimise CTR. CTR only measures if the card looked tempting. In skincare the gap between “tempting” and “suitable” can actually hurt someone.

Two extra metrics I care about:
- **Constraint violation rate** — target **zero**. This decides if a real retailer will use the system.
- **Low-confidence rate** — should stay non-zero and stable. Driving it to zero means the honesty check is broken.

**Technical answer**  
Offline metrics that can be calculated today (no labels needed):
- Constraint violation rate
- Catalogue coverage
- Intra-list diversity
- Novelty
- Latency (p50 / p95)
- Low-confidence rate
- Property precision@5 on a small golden set

NDCG / MAP / Recall need graded labels I do not have, so I do not report them.  
`request_id` is implemented end-to-end so online metrics can be added later.

---

## 4. What information should I collect *before* recommending?

**Business answer**  
Every question costs customers. Ask only the questions that change the answer the most.

**Must collect (hard constraints)**  
- Concern / goal (one signal is mandatory)  
- Ingredient avoidance (highest value field)  
- Budget (hard filter, easy to answer)  
- Product type (stops showing moisturisers when user wants a cleanser)

**Collect but treat as soft**  
- Skin type — people often mis-report it. Use only for ranking, never as a hard filter.  
- Brand preference — real but can create filter bubbles.

**Never collect as a form field — only detect and route out**  
- Pregnancy, medical conditions, prescription use, children’s use.  
  Asking “are you pregnant?” is invasive and creates sensitive data.  
  Instead: detect the words in free text and immediately say “please check with a doctor”. No products are shown.

**Technical answer**  
- Intake has four steps. Everything after the first can be skipped.
- Only one `/recommend` call at the end (not one call per step).
- Filter options come from live catalogue (`GET /products/facets`) so the UI never offers a filter that returns nothing.
- Safety gate is a simple keyword check in `safety.py`, tuned for high recall.

---

## 5. When should I *not* recommend?

**Business answer**  
Being able to say “I don’t know” is what makes the confident answers believable. A system that always returns something is not confident — it is just silent.

| Situation | Response |
|---|---|
| Medical / pregnancy / paediatric | Refuse completely. No products. Route to professional |
| Below relevance floor | “I am not confident” + suggest rephrasing |
| Fewer than 3 results after filters | Name the constraint + one-tap relax with real counts |
| Missing ingredient data | Never show a green tick for avoidance |
| Contradictory input | Say the conflict clearly |
| Budget mismatch | Filter by default, offer one clear opt-in |

**Hard rule:** ingredient exclusion is **never** offered as something to relax.  
Budget and skin type can be relaxed. Allergy rules cannot.

**Technical answer**  
```
message → safety gate (before any model) → refuse
        → embed + retrieve
        → top similarity < relevance floor → low-confidence state
        → filters + attrition tracking
        → results < 3 → low-confidence + relax options
```
Relax suggestions first count how many extra products each relaxed filter would give, so the button can say “+7 matches” before the user clicks.

---

## 6. How should I explain recommendations?

**Business answer**  
“Product A because…” is better than just “Product A”.  
But the **kind** of “because” matters. A nice-sounding but wrong explanation is worse than no explanation.

Only checkable explanations are worth building.

**Rule:** explanations describe **matching**, never **outcomes**.

| Never say | Say instead |
|---|---|
| “Treats your acne” | “Contains salicylic acid, commonly used for breakout-prone skin” |
| “For your skin type” | “Often suited to dry skin based on its ingredients” |
| “Fragrance-free” | “No fragrance ingredients found in the published list” |
| “Will reduce wrinkles” | “Contains retinol, commonly found in anti-ageing products” |

This is also a legal point. Cosmetic claims are regulated.

**Technical answer**  
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

---

## 7. What business KPI changes?

**Business answer**  
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

**Technical answer**  
Measurement plan:
1. Week 0 — only instrument. No user-facing change. Collect baselines.
2. Weeks 1–3 — A/B test (current search vs guided flow).
3. Primary metric: recommendation-to-cart rate.
4. Guardrails: return rate, low-confidence rate, latency, price distribution.
5. Decision rule written **before** looking at data: ship only if primary improves **and** no guardrail gets worse.

`request_id` is ready. Event emission is not implemented yet.

---

## 8. How will feedback improve recommendations?

**Business answer**  
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

**Technical answer**  
Two different loops:
- **Fast loop (minutes):** thumbs and reason codes drive alerts and debugging, never ranking. A spike in “contains avoided ingredient” means a filter is broken right now.
- **Slow loop (weeks–months):** kept purchases drive ranking updates, evaluated offline, released behind A/B tests. Never retrain on same-day clicks.

`/feedback` now carries `request_id`, rank, strategy, reason code and surface. Without `request_id` none of this works.

---

## 9. How do I know a recommendation failed?

**Business answer**  
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

**Technical answer**  
All signals are keyed to `request_id`.  
The API also self-reports failure: low-confidence flag, reason, and how many candidates each filter removed. This is unusual and useful.  
Self-reporting fields are implemented and visible in the UI tooltips. Behavioural events are named but not yet emitted.

---

## 10. What data should I collect for future ML?

**Business answer**  
Collect only what you will actually train on. In skincare, “collect everything and figure it out later” quickly becomes health data.

**Collect (with consent and ability to delete)**  
- Search / query text  
- Clicked products + rank (rank is required for position debiasing)  
- Skipped products above a click  
- Saved / wishlist  
- Feedback + reason code  
- Purchase + return outcome (the real objective)  
- Stated preferences from intake  

**Never collect or infer**  
- Medical conditions from browsing  
- Pregnancy or fertility status  
- Age beyond a simple adult check  
- Ethnicity or skin colour from product choices  
- Cross-device identity without consent  

**Governing rule:** store what the customer **told** you, never what you could **guess** about their body.

**Technical answer**  
- Session-scoped IDs by default. Account linking only on explicit opt-in.
- Rank stored with every interaction.
- Free-text chat has 90-day TTL and a real delete endpoint.
- Free text is scrubbed before any analytics.
- `/history` is now properly scoped to a session (the original version was a privacy bug).

Long-term training target: learning-to-rank model on **kept purchases**, using clicks only for candidate generation and position debiasing.

---

## One-line summary

**Rules decide the product. AI explains the choice.**

The interesting decisions were about where AI is **not** allowed to go.
