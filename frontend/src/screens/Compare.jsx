import { useStore } from '../App'
import { Link } from 'react-router-dom'
import { priceLabel } from '../components/ProductCard'
import { resolveAvoidTerms } from '../lib/avoid'
import InfoTip from '../components/InfoTip'

/** Comparison is where beauty purchase decisions actually get made — and the
 *  moment shoppers most often leave to Google. Keeping it in-session is
 *  directly conversion-protecting. */
export default function Compare() {
  const { compare, intake, toggleCompare } = useStore()
  if (compare.length < 2) {
    return <div className="shell empty"><p>Pick two or three products to compare.</p>
      <Link to="/results" className="btn ghost">Back to matches</Link></div>
  }

  const rows = [
    ['Price', (p) => priceLabel(p.price, p.price_currency) || 'Unavailable'],
    ['Type', (p) => p.product_type],
    ['Brand', (p) => p.brand],
    ['Often suited to', (p) => p.skin_type_confidence > 0 ? p.skin_types.join(', ') : 'Not enough data'],
    ['Built around', (p) => p.key_actives?.map((a) => a.name).join(', ') || '\u2014'],
    ['Ingredients', (p) => `${p.ingredients?.length || 0} listed`],
  ]

  const shared = compare.reduce((acc, p) =>
    acc === null ? new Set(p.ingredients) : new Set([...acc].filter((i) => p.ingredients.includes(i))), null)

  return (
    <div className="shell" style={{ paddingTop: 'var(--s6)', paddingBottom: 120 }}>
      <div className="eyebrow">Side by side</div>
      <h1 style={{ fontSize: '2rem', marginTop: 8, marginBottom: 'var(--s6)' }}>Comparing {compare.length}</h1>

      <table className="compare-table">
        <thead>
          <tr><th></th>{compare.map((p) => (
            <th key={p.id} style={{ width: 'auto' }}>
              <Link to={`/product/${p.id}`} style={{ fontFamily: 'var(--display)', fontSize: 15, textTransform: 'none', letterSpacing: 0, color: 'var(--ink)' }}>
                {p.product_name}
              </Link>
              <button className="linkbtn" style={{ display: 'block', marginTop: 6 }} onClick={() => toggleCompare(p)}>Remove</button>
            </th>))}</tr>
        </thead>
        <tbody>
          {rows.map(([label, fn]) => (
            <tr key={label}><th>{label}</th>{compare.map((p) => <td key={p.id}>{fn(p)}</td>)}</tr>
          ))}
          {intake.avoid.map((term) => {
            const { label, patterns } = resolveAvoidTerms(term)
            return (
              <tr key={term}>
                <th>No {label}</th>
                {compare.map((p) => {
                  const hits = (p.ingredients || []).filter((i) => patterns.some((x) => i.includes(x)))
                  return <td key={p.id} style={{ color: hits.length ? 'var(--clay)' : 'var(--pine)' }}>
                    {hits.length ? `Contains: ${hits.slice(0, 3).join(', ')}` : 'Not found \u2713'}
                  </td>
                })}
              </tr>
            )
          })}
          <tr>
            <th>Shared ingredients</th>
            <td colSpan={compare.length} style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
              {shared && shared.size ? [...shared].slice(0, 24).join(' \u00b7 ') : 'None in common'}
            </td>
          </tr>
        </tbody>
      </table>

      <p className="note" style={{ marginTop: 'var(--s6)' }}>
        Ingredient lists are shown as published by the retailer. Formulations change —
        check the pack. <InfoTip topic="product" callLabel="batch" />
      </p>
    </div>
  )
}
