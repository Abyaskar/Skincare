import { Link } from 'react-router-dom'
import InfoTip from './InfoTip'
import { resolveAvoidTerms } from '../lib/avoid'

/** Price is nullable by design — an unknown price is never rendered as £0.00. */
export function priceLabel(price, currency = 'GBP') {
  if (price === null || price === undefined) return null
  const symbol = { GBP: '\u00a3', USD: '$', EUR: '\u20ac', INR: '\u20b9' }[currency] || ''
  return `${symbol}${price.toFixed(2)}`
}

/**
 * THE SIGNATURE ELEMENT.
 *
 * The dataset has no product photography, so rather than grey placeholder
 * boxes each card is grounded in the one piece of rich data every product
 * does have: its real INCI ingredient list. Set tiny, held back to a whisper —
 * and anything the customer asked about lifted to full weight in pine.
 *
 * The card doesn't claim a match, it shows the evidence for one.
 */
function IngredientGround({ product, highlight = [] }) {
  const patterns = highlight.flatMap((t) => resolveAvoidTerms(t).patterns)
  const items = (product.ingredients || []).slice(0, 90)
  return (
    <div className="card-ground">
      <div className="ground-text" aria-hidden="true">
        {items.length === 0
          ? 'ingredient list not published for this product \u00b7 '.repeat(14)
          : items.map((ing, i) => {
              const hit = patterns.some((p) => ing.includes(p))
              return (
                <span key={i}>
                  {hit ? <mark>{ing}</mark> : ing}
                  {i < items.length - 1 ? ' \u00b7 ' : ''}
                </span>
              )
            })}
      </div>
      <div className="ground-label">
        <div className="ground-type">{product.product_type}</div>
      </div>
    </div>
  )
}

function Strength({ level }) {
  if (!level) return null
  const n = level === 'strong' ? 3 : level === 'moderate' ? 2 : 1
  return (
    <span className={`strength ${level}`} title={`${level} match`} aria-label={`${level} match`}>
      {[0, 1, 2].map((i) => <i key={i} className={i < n ? 'on' : ''} />)}
    </span>
  )
}

export default function ProductCard({
  product,
  requestId,
  strategy,
  onWhy,
  onCompare,
  compared = false,
  highlight = [],
}) {
  const price = priceLabel(product.price, product.price_currency)
  const topReason = product.match_reasons?.find((r) => r.kind === 'pass')
    || product.match_reasons?.find((r) => r.kind === 'info')
  const caution = product.match_reasons?.find((r) => r.kind === 'caution')

  return (
    <article className="card">
      <IngredientGround product={product} highlight={highlight} />

      <div className="card-body">
        <div className="card-brand">
          {product.brand}
          {/* Brand is derived from the product name for ~54% of this catalogue,
              so anything below full confidence is marked as our guess. */}
          {product.brand_confidence < 1 && <InfoTip topic="derived" />}
        </div>

        <Link to={`/product/${product.id}`} className="card-name" style={{ textDecoration: 'none' }}>
          {product.product_name}
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {price
            ? <span className="card-price">{price}</span>
            : <span className="card-price unknown">Price unavailable</span>}
          <Strength level={product.match_strength} />
        </div>

        {topReason && <div className="reason-chip">{topReason.label}</div>}
        {caution && <div className="reason-chip caution">{caution.label}</div>}

        <div className="card-actions">
          {onWhy && (
            <button className="btn ghost small" onClick={() => onWhy(product)}>
              Why this?
            </button>
          )}
          {onCompare && (
            <button
              className="btn ghost small"
              aria-pressed={compared}
              onClick={() => onCompare(product)}
              style={compared ? { borderColor: 'var(--pine)', color: 'var(--pine)' } : undefined}
            >
              {compared ? 'Comparing' : 'Compare'}
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
