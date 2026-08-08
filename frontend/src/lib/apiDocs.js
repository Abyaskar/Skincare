/**
 * The two tiers of every ⓘ tooltip.
 *
 * `plain` is what a shopper reads: no jargon, no HTTP verbs, answering the
 * question they'd actually have at that point on the screen.
 *
 * `why` is the engineering tier, collapsed behind one tap. It explains the
 * method choice in plain English INCLUDING the trade-offs — an explanation
 * that only lists advantages reads as marketing, not as engineering.
 */
export const API_DOCS = {
  recommend: {
    plain:
      'We take what you told us and find products that fit. Your budget and anything you asked to avoid are strict rules — nothing that breaks them can appear here, however well it scores otherwise.',
    verb: 'POST',
    route: '/recommend',
    why:
      'POST rather than GET for three reasons. The body is a nested object — filters, arrays of ingredients — which does not fit cleanly in a URL. It is personal: URLs get logged by proxies and browsers, and someone\u2019s allergy list should not sit in a server log. And it is not a fixed address anyone would bookmark. GET means "give me this thing"; POST means "here is my situation, work something out".',
    layers: [
      ['Rules', 'Budget, skin type, brand, product type and ingredient exclusions are MongoDB filters, applied before ranking and re-checked in Python afterwards.'],
      ['Vectors', 'Your description is embedded with all-MiniLM-L6-v2 (384 dimensions) and matched against a FAISS index of 1,138 products.'],
      ['Fusion', 'Reciprocal Rank Fusion blends the semantic ranking with ingredient similarity, 60/40. It combines rankings rather than raw scores, so the top result is not artificially pinned at 1.0 on every query.'],
      ['Model', 'None in this path. No language model takes any part in choosing or ordering products.'],
    ],
  },
  search: {
    plain:
      'Describe what you want in your own words. We match on meaning rather than exact words, so "tight after washing" finds hydrating products even though no product name contains the word "tight".',
    verb: 'POST',
    route: '/search',
    why:
      'This is the debatable one. Search "should" be a GET \u2014 GETs are shareable and bookmarkable, and a shareable search URL has real commercial value. It is POST here because the body carries arrays (brands, product types) plus a long free-text query, and embedding a query costs the same whether the string was seen before or not, so there is little to cache. In production I would add a GET variant with query parameters for the shareable case and keep POST for the complex one.',
    layers: [
      ['Purpose', 'Reduce the zero-result rate. Every empty search is a lost customer who had already told you they wanted to buy something.'],
      ['Known gap', 'Embeddings are weak on proper nouns, so an exact brand or product-name search would be better served by a lexical (BM25) path merged with this one.'],
    ],
  },
  products: {
    plain:
      'The full catalogue, filtered and paged. Nothing personalised \u2014 this is here for when you would rather look around yourself.',
    verb: 'GET',
    route: '/products',
    why:
      'GET because it only reads. The same request always returns the same answer, so it can be cached, bookmarked, shared and safely re-fetched by a browser or a crawler. Filters live in the query string precisely so those URLs are shareable: /products?brand=cerave&max_price=20 is a link you can send someone.',
    layers: [
      ['Strategic role', 'The only endpoint with no AI in its path, which makes it the fallback. If the vector index fails to load or the language model is down, the shop degrades to a filtered catalogue instead of an error page.'],
    ],
  },
  product: {
    plain:
      'Everything published about one product, including the full ingredient list \u2014 with your own avoid-rules re-checked against it.',
    verb: 'GET',
    route: '/products/{id}',
    why:
      'GET with the ID in the path, because the product IS the resource and the URL is its permanent address. That is what makes it linkable, cacheable and indexable \u2014 three things a product page needs. Putting the ID in a request body would break all three.',
    layers: [
      ['Rule we hold to', 'If a product has no published ingredient list, the avoid-check disappears rather than showing a green tick. An unearned reassurance on an allergy question is worse than no feature at all.'],
    ],
  },
  chat: {
    plain:
      'Ask anything a form cannot capture \u2014 how to layer products, what an ingredient is usually used for. Answers come from this catalogue, not from the open internet.',
    verb: 'POST',
    route: '/chat',
    why:
      'POST because it creates something: each message is stored as a history record with its own timestamp, so it is not a read. It is also the only endpoint that costs real money per call, which is a second reason it should never be a cacheable, pre-fetchable GET.',
    layers: [
      ['Safety gate', 'A deterministic keyword check runs BEFORE the model. Medical, prescription, pregnancy and paediatric questions return a "please see a professional" response and no products at all. Never left to the model to police itself.'],
      ['Grounding', 'Retrieval-augmented: the question is embedded, the closest products are pulled from FAISS, and the model receives only those as context.'],
      ['Confidence floor', 'If nothing retrieved is close enough, we say so rather than letting a fluent model improvise over thin grounding.'],
      ['Failover', 'Gemini, then OpenAI, then a retrieval-only answer. You should never see an error because one vendor had a bad minute.'],
    ],
  },
  feedback: {
    plain:
      'Tells us when a suggestion missed. The reason matters more than the thumb \u2014 "contains something I avoid" is a bug report, and it gets treated like one.',
    verb: 'POST',
    route: '/feedback',
    why:
      'POST because it creates a new record. Two thumbs-down on the same product a week apart are two facts, not one overwritten one \u2014 which is exactly what POST means, and why this is not a PUT.',
    layers: [
      ['What it carries', 'request_id, rank, strategy, reason code and surface. Without request_id you cannot link feedback back to the recommendation that produced it, and recommendation acceptance rate becomes uncomputable.'],
    ],
  },
  history: {
    plain:
      'Your previous questions in this browser. You can clear them at any time, and clearing actually deletes them.',
    verb: 'GET',
    route: '/history',
    why:
      'GET because it only reads, with the session in a query parameter rather than the path \u2014 history is a filtered view over a collection rather than a single addressable thing.',
    layers: [
      ['Security fix', 'session_id used to be optional with no authentication, so calling this bare returned everyone\u2019s chat text, including free-text descriptions of their skin. It is now required. In production it would also be bound to a signed token and carry a 90-day expiry.'],
    ],
  },
  facets: {
    plain:
      'The filter options here are read from the live catalogue, so we never offer you a filter that returns nothing.',
    verb: 'GET',
    route: '/products/facets',
    why:
      'GET and cacheable. It exists so the interface never hardcodes brand lists or price ranges. A frontend that knows more about the data than the database does will rot the first time the catalogue changes.',
    layers: [],
  },
  derived: {
    plain:
      'This came from us, not from the brand. We worked it out from the product\u2019s ingredient list, so treat it as a helpful signal rather than a fact.',
    verb: null,
    route: null,
    why:
      'The source dataset has five columns: name, URL, type, ingredients, price. Brand and skin-type fit are both derived during preprocessing \u2014 brand from the product name, skin-type fit from ingredient keywords. Ingredient presence says nothing about concentration or formulation, which is why the label is always "often suited to" and never "for your skin type".',
    layers: [],
  },
  ground: {
    plain:
      'The pattern behind each product is its real ingredient list. Anything you asked about is picked out in green, so you can see the match rather than take our word for it.',
    verb: null,
    route: null,
    why:
      'The dataset has no product photography. Rather than ship grey placeholder boxes, the card is grounded in the one piece of rich data every product does have \u2014 its INCI list. It is honest, it is specific to each product, and it does a job a stock photo could not: it shows the evidence for the recommendation.',
    layers: [],
  },
}
