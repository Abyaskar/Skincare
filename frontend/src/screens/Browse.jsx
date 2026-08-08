import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../App'
import ProductCard from '../components/ProductCard'
import InfoTip from '../components/InfoTip'

/**
 * Search + browse on one screen.
 *
 * Browse exists for the significant share of shoppers who refuse funnels, and
 * because it is the only path with no AI in it — the fallback when the vector
 * index or the model is unavailable.
 */
export default function Browse() {
  const { facets, toggleCompare, compare } = useStore()
  const [mode, setMode] = useState('browse')
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [type, setType] = useState('')
  const [sort, setSort] = useState('name')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (mode !== 'browse') return
    setLoading(true)
    api.products({ page, page_size: 12, product_type: type || undefined, sort })
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [mode, page, type, sort])

  const runSearch = async (e) => {
    e?.preventDefault()
    if (!q.trim()) return
    setMode('search'); setLoading(true)
    try { setData(await api.search({ query: q, top_k: 12 })) } catch { /* handled below */ }
    setLoading(false)
  }

  const items = data?.items || data?.products || []

  return (
    <div className="shell" style={{ paddingTop: 'var(--s6)', paddingBottom: 'var(--s9)' }}>
      <form onSubmit={runSearch} style={{ display: 'flex', gap: 10, marginBottom: 'var(--s5)' }}>
        <input className="textinput" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Describe what you want \u2014 e.g. something for skin that feels tight after washing" />
        <button className="btn" type="submit">Search</button>
        <span style={{ alignSelf: 'center' }}>
          <InfoTip topic={mode === 'search' ? 'search' : 'products'}
            callLabel={mode === 'search' ? 'search' : 'products'} align="right" />
        </span>
      </form>

      {mode === 'browse' && (
        <div className="summary">
          <span className="eyebrow">Filter</span>
          <select value={type} onChange={(e) => { setType(e.target.value); setPage(1) }} style={{ width: 'auto' }}>
            <option value="">All types</option>
            {(facets?.product_types || []).map((t) => <option key={t}>{t}</option>)}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} style={{ width: 'auto' }}>
            <option value="name">A\u2013Z</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
          </select>
          <span style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--ink-soft)' }}>
            {data?.total ? `${data.total.toLocaleString()} products` : ''}
          </span>
        </div>
      )}

      {mode === 'search' && (
        <div className="summary">
          <span className="eyebrow">Results for</span>
          <span className="tag">"{data?.query || q}"</span>
          <button className="linkbtn" onClick={() => { setMode('browse'); setQ('') }}>Clear</button>
          <Link to="/find" className="linkbtn" style={{ marginLeft: 'auto' }}>
            Want these matched to your skin? \u2192
          </Link>
        </div>
      )}

      {loading && <p className="spinner">LOADING\u2026</p>}

      {data?.low_confidence && (
        <div className="panel" style={{ marginBottom: 'var(--s5)' }}>
          <p style={{ fontFamily: 'var(--display)', fontSize: '1.2rem', margin: 0 }}>Nothing here is a close match.</p>
          <p style={{ fontSize: 14, color: 'var(--ink-soft)', marginTop: 8, marginBottom: 0 }}>
            A nearest-neighbour search always returns something, so we check how close it
            actually was — and this wasn't close. Try different words, or browse by category.
          </p>
        </div>
      )}

      <div className="grid">
        {items.map((p) => (
          <ProductCard key={p.id} product={p} onCompare={toggleCompare}
            compared={!!compare.find((c) => c.id === p.id)} />
        ))}
      </div>

      {mode === 'browse' && data && (
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 'var(--s7)' }}>
          <button className="btn ghost small" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span style={{ alignSelf: 'center', fontFamily: 'var(--mono)', fontSize: 12 }}>
            {page} / {Math.max(1, Math.ceil((data.total || 1) / 12))}
          </span>
          <button className="btn ghost small"
            disabled={page >= Math.ceil((data.total || 1) / 12)}
            onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </div>
  )
}
