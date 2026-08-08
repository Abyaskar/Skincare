import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, sessionId } from '../lib/api'
import { useStore } from '../App'
import ProductCard, { priceLabel } from '../components/ProductCard'
import InfoTip from '../components/InfoTip'
import { resolveAvoidTerms } from '../lib/avoid'

export default function ProductDetail() {
  const { id } = useParams()
  const { intake, toggleCompare, compare } = useStore()
  const [product, setProduct] = useState(null)
  const [similar, setSimilar] = useState([])
  const [filter, setFilter] = useState('')
  const [sent, setSent] = useState(false)

  useEffect(() => {
    setProduct(null)
    api.product(id).then(setProduct).catch(() => {})
    api.similar(id).then((r) => setSimilar(r.products || [])).catch(() => {})
  }, [id])

  if (!product) return <div className="shell" style={{ padding: '80px 24px' }}><p className="spinner">LOADING\u2026</p></div>

  const price = priceLabel(product.price, product.price_currency)
  const avoidChecks = intake.avoid.map((term) => {
    const { label, patterns } = resolveAvoidTerms(term)
    const hits = (product.ingredients || []).filter((i) => patterns.some((p) => i.includes(p)))
    return { label, hits, checkable: (product.ingredients || []).length > 0 }
  })
  const shown = (product.ingredients || []).filter((i) => i.includes(filter.toLowerCase()))

  return (
    <div className="shell" style={{ paddingTop: 'var(--s6)', paddingBottom: 'var(--s9)' }}>
      <Link to="/results" className="linkbtn">\u2190 Back to matches</Link>

      <div style={{ display: 'grid', gap: 'var(--s7)', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.1fr)', marginTop: 'var(--s5)' }}>
        <div>
          <div className="card-brand" style={{ marginBottom: 8 }}>
            {product.brand}
            {product.brand_confidence < 1 && <InfoTip topic="derived" />}
          </div>
          <h1 style={{ fontSize: 'clamp(1.8rem,4vw,2.6rem)' }}>{product.product_name}</h1>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 18, marginTop: 'var(--s4)' }}>
            {price || 'Price unavailable'} <InfoTip topic="product" callLabel="product" />
          </div>
          <p className="note" style={{ marginTop: 10 }}>
            Price is from our catalogue snapshot and may be out of date.
          </p>

          {product.skin_types?.length > 0 && product.skin_type_confidence > 0 && (
            <p style={{ marginTop: 'var(--s5)' }}>
              <span className="eyebrow">Often suited to</span><br />
              {product.skin_types.join(', ')} skin
              {product.skin_type_confidence < 0.7 && ' — a weak signal, from one ingredient'}
            </p>
          )}

          {avoidChecks.length > 0 && (
            <>
              <div className="eyebrow" style={{ margin: '28px 0 10px' }}>Your rules, re-checked here</div>
              <ul className="reason-list">
                {avoidChecks.map((c) => (
                  <li key={c.label}>
                    <span className={`reason-icon ${!c.checkable ? 'caution' : c.hits.length ? 'caution' : 'pass'}`}>
                      {!c.checkable ? '!' : c.hits.length ? '!' : '\u2713'}
                    </span>
                    <div className="reason-body">
                      <strong>
                        {!c.checkable ? `Can't check for ${c.label}`
                          : c.hits.length ? `Contains ${c.label}`
                          : `No ${c.label} found`}
                      </strong>
                      <span>{c.hits.length ? c.hits.join(', ') : 'Matched against the published list.'}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 'var(--s6)', flexWrap: 'wrap' }}>
            <a className="btn" href={product.product_url} target="_blank" rel="noreferrer">View at retailer</a>
            <button className="btn ghost" onClick={() => toggleCompare(product)}>
              {compare.find((c) => c.id === product.id) ? 'Comparing' : 'Compare'}
            </button>
            <button className="btn ghost" disabled={sent}
              onClick={async () => {
                await api.feedback({ product_id: product.id, feedback_type: 'helpful', surface: 'product', session_id: sessionId() }).catch(() => {})
                setSent(true)
              }}>
              {sent ? 'Thanks' : 'Useful'} <InfoTip topic="feedback" callLabel="feedback" />
            </button>
          </div>
        </div>

        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Full ingredient list — {product.ingredients?.length || 0} items
          </div>
          <input className="textinput" placeholder="Search this list\u2026" value={filter}
            onChange={(e) => setFilter(e.target.value)} style={{ marginBottom: 'var(--s4)' }} />
          <div className="ingredient-list">
            {shown.map((i, k) => {
              const bad = avoidChecks.some((c) => c.hits.includes(i))
              return <span key={k} className={bad ? 'bad' : filter && i.includes(filter.toLowerCase()) ? 'hit' : ''}>{i}</span>
            })}
            {shown.length === 0 && <p className="note">No ingredient matches "{filter}".</p>}
          </div>
        </div>
      </div>

      {similar.length > 0 && (
        <>
          <hr className="rule" />
          <h2 style={{ marginBottom: 'var(--s5)' }}>Built from similar ingredients</h2>
          <div className="grid">
            {similar.map((p) => <ProductCard key={p.id} product={p} onCompare={toggleCompare}
              compared={!!compare.find((c) => c.id === p.id)} highlight={intake.avoid} />)}
          </div>
        </>
      )}

      <p className="note caution" style={{ marginTop: 'var(--s7)' }}>
        Patch-test anything new. If you have a diagnosed skin condition, are pregnant, or
        are using a prescription treatment, check with a professional first.
      </p>
    </div>
  )
}
