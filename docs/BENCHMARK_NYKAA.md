# Benchmark: Nykaa, Sephora, and why this UI diverges

*The assignment's bonus asks you to mimic an existing product and compare.
This build benchmarks against Nykaa and Sephora but deliberately does not clone
either. The reasoning is below, because "we didn't do the bonus" is a weaker
answer than "we did the analysis and chose differently."*

---

## The reference points

| Platform | Discovery model | Explanation | Constraint filtering |
|---|---|---|---|
| **Nykaa** | Category browse + search + editorial. Personalisation is behavioural (viewed / bought) | None per-recommendation | Category, brand, price, "concern" tags. No ingredient exclusion |
| **Sephora** | Similar, plus a skin-profile ("Beauty Insider" preferences) that filters some surfaces | Light — "matches your profile" | Skin type, concern, "free from" tags on *some* products, supplied by brands |
| **This build** | Guided intake → explained shortlist. Chat is secondary | Per-product, rule-derived, checkable | Ingredient exclusion as a hard, expanded, safety-grade filter |

---

## Similarities

- Product-grid results, filter sidebar, pagination, compare — the conventions
  are conventions for good reasons and there is no value in reinventing them.
- Concern-led entry ("dryness", "breakouts") rather than category-led, which is
  how Sephora's and Nykaa's skin quizzes both open.
- Search is a first-class surface, not just a fallback from browse.

## Differences, and the reasoning

**1. The shortlist is short, and explained.** Nykaa returns hundreds of results
sorted by popularity. This returns nine, each with a reason attached. That is a
worse metric on "results returned" and a better outcome on time-to-decision.

**2. Ingredient exclusion is a real filter, not a marketing tag.** Sephora's
"fragrance free" flag is supplied by brands per-product. Here it is computed
from the ingredient list at query time and expanded through a synonym map —
`fragrance` matches `parfum`, `linalool`, `limonene` and eleven others.
Measured on this catalogue: **747 of 1,138 products** contain a fragrance-group
ingredient. A tag-based approach depends on every brand having declared it
honestly; a computed approach doesn't.

**3. The system is allowed to return nothing.** Neither reference platform has
a "we don't have a good match" state. Both will always fill the grid. That is a
commercial decision on their part and a trust decision on ours.

**4. No product photography — by necessity, then by design.** Both references
are image-led; the dataset has no images. Rather than grey placeholders, each
card is grounded in that product's real INCI list with matched ingredients
highlighted. It turns the constraint into the most distinctive element on the
page, and it does something a stock photo cannot: it shows the evidence for the
recommendation.

**5. No urgency, no discounting, no "only 2 left".** Both references lean on
scarcity and price anchoring. This build has none, because the customer it
serves converts on trust rather than on pressure.

---

## Where the references are better

Worth being straight about — the comparison is only credible if it cuts both ways.

- **Images, reviews, ratings, and social proof.** Enormous conversion drivers.
  This build has none of them, and no amount of ranking quality substitutes.
- **Stock, delivery, returns, real checkout.** Nykaa is a shop; this is a
  discovery layer with a link out.
- **Editorial and video content.** A genuine differentiator for both, and a
  real reason customers return.
- **Brand-name search.** Both handle exact product-name lookup far better than
  a pure embedding index does — a known gap here (see `TEST_CASES.md` F3).
- **Scale.** Millions of SKUs, ANN indexes, real personalisation trained on
  real purchase histories.

---

## Where this implementation could improve

1. **Hybrid lexical + vector retrieval** so brand-name queries work.
2. **Images**, even scraped `og:image`, before any real user test.
3. **Inventory and country compliance** as deterministic filters.
4. **A Nykaa-styled theme** — the design system is tokenised, so this is a
   second CSS variable file, not a rebuild. Worth doing if hours remain.
5. **Real behavioural personalisation**, once there is purchase and return data
   to learn from.

---

## The one-line argument

> Nykaa and Sephora are optimised for a catalogue with images, reviews and
> stock, serving a browsing customer. This is optimised for a catalogue with
> nothing but ingredient lists, serving a customer with a constraint. Cloning
> the first would have meant inheriting a design whose central assets I don't
> have — so I benchmarked against them, took the conventions worth taking, and
> diverged where the data forced a different answer.
