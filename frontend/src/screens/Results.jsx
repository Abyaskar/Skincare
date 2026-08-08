import { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStore } from '../App'
import { api, sessionId } from '../lib/api'
import ProductCard from '../components/ProductCard'
import WhyDrawer from '../components/WhyDrawer'
import InfoTip from '../components/InfoTip'

/** Turn the intake answers into a /recommend body. */
function buildRequest(intake) {
  const query = [intake.text, ...intake.concerns].filter(Boolean).join(', ')
    || 'a good everyday skincare product'
  return {
    query,
    strategy: 'hybrid',
    top_k: 9,
    diversify: true,
    filters: {
      max_price: intake.max_price ?? null,
      min_price: intake.min_price ?? null,
      skin_type: intake.skin_type ?? null,
      ingredients_exclude: intake.avoid,
      ingredients_include: intake.include,
      product_types: intake.product_types,
      brands: [],
    },
  }
}

export default function Results() {
  const { intake, setIntake, result, setResult, compare, toggleCompare } = useStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [why, setWhy] = useState(null)
  const [toast, setToast] = useState(null)
  const navigate = useNavigate()

  const run = useCallback(async (overrides = {}) => {
    setLoading(true); setError(null)
    try {
      const body = buildRequest({ ...intake, ...overrides })
      setResult(await api.recommend(body))
    } catch (e) { setError(e.message) }
    setLoading(false)
  }, [intake, setResult])

  useEffect(() => { run() /* eslint-disable-next-line */ }, [
    intake.text, intake.concerns.join(), intake.skin_type,
    intake.max_price, intake.avoid.join(), intake.product_types.join(),
  ])

  const relax = (filterName) => {
    const patch = {
      max_price: { max_price: null }, min_price: { min_price: null },
      skin_type: { skin_type: null }, product_types: { product_types: [] },
      brands: {}, ingredients_include: { include: [] },
    }[filterName] || {}
    setIntake({ ...intake, ...patch })
  }

  const sendFeedback = async (product, type) => {
    try {
      await api.feedback({
        product_id: product.id, feedback_type: type,
        request_id: result?.request_id, rank: product.rank,
        strategy: result?.strategy, surface: 'recommendation',
        session_id: sessionId(),
      })
      setToast('Thanks — noted.')
      setTimeout(() => setToast(null), 2200)
    } catch { /* feedback must never block the customer */ }
  }

  const tags = []
  if (intake.skin_type) tags.push([`${intake.skin_type} skin`, () => setIntake({ ...intake, skin_type: null })])
  if (intake.max_price) tags.push([`under \u00a3${intake.max_price}`, () => setIntake({ ...intake, max_price: null })])
  intake.avoid.forEach((a) => tags.push([`no ${a}`, () => setIntake({ ...intake, avoid: intake.avoid.filter((x) => x !== a) })]))
  intake.product_types.forEach((t) => tags.push([t, () => setIntake({ ...intake, product_types: intake.product_types.filter((x) => x !== t) })]))

  return (
    <div className="shell" style={{ paddingTop: 'var(--s6)', paddingBottom: 'var(--s9)' }}>
      <div className="summary">
        <span className="eyebrow" style={{ marginRight: 8 }}>Matched on</span>
        {intake.text && <span className="tag">"{intake.text.slice(0, 44)}"</span>}
        {intake.concerns.map((c) => <span key={c} className="tag">{c}</span>)}
        {tags.map(([label, remove]) => (
          <span key={label} className="tag">{label}<button onClick={remove} aria-label={`Remove ${label}`}>\u00d7</button></span>
        ))}
        <Link to="/find" className="linkbtn" style={{ marginLeft: 'auto' }}>Edit answers</Link>
      </div>

      {loading && <p className="spinner">CHECKING THE CATALOGUE\u2026</p>}
      {error && <div className="note caution">{error}</div>}

      {!loading && result && (
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 'var(--s5)' }}>
            <h2>{result.low_confidence ? 'Not a confident match' : `${result.total} matches`}</h2>
            <InfoTip topic="recommend" callLabel="recommend" />
            <span className="eyebrow" style={{ marginLeft: 'auto' }}>{result.took_ms} MS</span>
          </div>

          {/* The screen most demos skip: an honest dead end with a way out. */}
          {result.low_confidence && (
            <div className="panel" style={{ marginBottom: 'var(--s6)' }}>
              <p style={{ fontFamily: 'var(--display)', fontSize: '1.2rem' }}>
                {reasonHeadline(result)}
              </p>
              <p style={{ color: 'var(--ink-soft)', fontSize: 14 }}>{reasonDetail(result, intake)}</p>
              {result.relax_suggestions?.length > 0 && (
                <>
                  <div className="eyebrow" style={{ margin: '18px 0 10px' }}>Loosen one rule</div>
                  <div className="chip-row">
                    {result.relax_suggestions.map((s) => (
                      <button key={s.filter_name} className="chip" onClick={() => relax(s.filter_name)}>
                        {s.label} <strong style={{ color: 'var(--pine)' }}>+{s.result_count}</strong>
                      </button>
                    ))}
                  </div>
                </>
              )}
              <p className="note" style={{ marginTop: 20 }}>
                We'd rather show you nothing than the wrong thing. Anything you asked to
                avoid stays excluded — that's a safety rule, not a preference, so it's
                never offered as something to loosen.
              </p>
            </div>
          )}

          <div className="grid">
            {result.products.map((p) => (
              <ProductCard key={p.id} product={p} highlight={[...intake.avoid, ...intake.include]}
                onWhy={setWhy} onCompare={toggleCompare}
                compared={!!compare.find((c) => c.id === p.id)} />
            ))}
          </div>

          {result.products.length === 0 && !result.relax_suggestions?.length && (
            <div className="empty">
              <p>Nothing in the catalogue satisfies every rule you set.</p>
              <button className="btn ghost" onClick={() => navigate('/find')}>Change your answers</button>
            </div>
          )}

          <p className="note" style={{ marginTop: 'var(--s7)' }}>
            Suggestions based on published ingredient lists and the preferences you set.
            Not medical advice, and ingredient data may be incomplete — check the label
            before buying if you have an allergy.
          </p>
        </>
      )}

      {why && <WhyDrawer product={why} filters={result?.filters_applied} onClose={() => setWhy(null)} onFeedback={sendFeedback} />}
      {toast && <div className="tray" style={{ justifyContent: 'center' }}>{toast}</div>}
    </div>
  )
}

function reasonHeadline(r) {
  return {
    no_results: "Nothing here fits all of that.",
    too_few_results: "Only a couple of things fit all of that.",
    below_relevance_floor: "I'm not confident about this one.",
  }[r.low_confidence_reason] || "I'm not confident about this one."
}

function reasonDetail(r, intake) {
  if (r.low_confidence_reason === 'below_relevance_floor') {
    return "Nothing in the catalogue is a close match for what you described. Rather than show you the least-bad option, here's the honest answer — try describing your skin differently, or browse by category."
  }
  const worst = Object.entries(r.filter_attrition || {}).sort((a, b) => b[1] - a[1])[0]
  const names = {
    max_price: 'your budget', skin_type: 'skin type', ingredients_exclude: 'what you asked to avoid',
    product_types: 'product type', brands: 'brand', ingredients_include: 'the ingredients you asked for',
  }
  if (worst) return `${worst[1]} of the closest products were ruled out by ${names[worst[0]] || worst[0]}.`
  return `We checked ${r.candidates_before_filters} candidates and ${r.total} passed every rule.`
}
