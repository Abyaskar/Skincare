import InfoTip from './InfoTip'
import { priceLabel } from './ProductCard'

/**
 * "Why this was recommended".
 *
 * Every fact here is generated from the filters that actually ran and from
 * fields on the product document. Nothing is written by a language model, so
 * the panel is auditable, it works when the LLM is down, and it describes
 * MATCHING rather than OUTCOMES — "contains salicylic acid, commonly used in
 * products aimed at breakout-prone skin", never "clears acne". Cosmetic claims
 * are regulated; a generated one could reclassify the product.
 */
export default function WhyDrawer({ product, filters, onClose, onFeedback }) {
  if (!product) return null
  const icon = { pass: '\u2713', caution: '!', info: '\u00b7' }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Why this was recommended">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 16 }}>
          <div>
            <div className="eyebrow">Why this was recommended</div>
            <h2 style={{ marginTop: 8 }}>{product.product_name}</h2>
          </div>
          <button className="linkbtn" onClick={onClose}>Close</button>
        </div>

        <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 14 }}>
          {priceLabel(product.price, product.price_currency) || 'Price unavailable'}
        </div>

        <hr className="rule" style={{ margin: '20px 0' }} />

        <div className="eyebrow" style={{ marginBottom: 10 }}>
          What you told us
        </div>
        <div className="chip-row" style={{ marginBottom: 24 }}>
          {summariseFilters(filters).map((t) => (
            <span key={t} className="chip" style={{ pointerEvents: 'none' }}>{t}</span>
          ))}
          {summariseFilters(filters).length === 0 && (
            <span className="note">You didn't set any filters, so this is matched on your description alone.</span>
          )}
        </div>

        <div className="eyebrow" style={{ marginBottom: 6 }}>
          What we checked <InfoTip topic="recommend" callLabel="recommend" />
        </div>
        <ul className="reason-list">
          {product.match_reasons?.map((r, i) => (
            <li key={i}>
              <span className={`reason-icon ${r.kind}`}>{icon[r.kind]}</span>
              <div className="reason-body">
                <strong>{r.label}</strong>
                {r.detail && <span>{r.detail}</span>}
              </div>
            </li>
          ))}
          {(!product.match_reasons || product.match_reasons.length === 0) && (
            <li><span className="reason-icon info">\u00b7</span>
              <div className="reason-body"><strong>Matched on your description</strong>
                <span>No filters were set, so there's nothing else to check against.</span></div>
            </li>
          )}
        </ul>

        {product.key_actives?.length > 0 && (
          <>
            <div className="eyebrow" style={{ margin: '28px 0 10px' }}>What this formula is built around</div>
            <div className="stack">
              {product.key_actives.map((a) => (
                <div key={a.name} className="note">
                  <strong style={{ fontWeight: 500 }}>{a.name}</strong> — {a.blurb}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="note caution" style={{ marginTop: 28 }}>
          Ingredient information comes from the retailer's product listing and may be
          incomplete. Skin-type fit is inferred from ingredients, not confirmed by the
          brand. This is product discovery, not medical advice.
        </div>

        {onFeedback && (
          <div style={{ marginTop: 28 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              Was this useful? <InfoTip topic="feedback" callLabel="feedback" />
            </div>
            <div className="chip-row">
              <button className="chip" onClick={() => onFeedback(product, 'helpful')}>Helpful</button>
              <button className="chip" onClick={() => onFeedback(product, 'not_helpful')}>Not for me</button>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

function summariseFilters(f = {}) {
  const out = []
  if (f.skin_type) out.push(`${f.skin_type} skin`)
  if (f.max_price) out.push(`under \u00a3${f.max_price}`)
  if (f.min_price) out.push(`over \u00a3${f.min_price}`)
  ;(f.ingredients_exclude || []).forEach((i) => out.push(`no ${i}`))
  ;(f.ingredients_include || []).forEach((i) => out.push(`with ${i}`))
  ;(f.product_types || []).forEach((t) => out.push(t))
  ;(f.brands || []).forEach((b) => out.push(b))
  return out
}
