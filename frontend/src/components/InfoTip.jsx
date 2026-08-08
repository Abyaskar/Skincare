import { useState, useRef, useEffect } from 'react'
import { API_DOCS } from '../lib/apiDocs'
import { getCall } from '../lib/api'

/**
 * The two-tier tooltip.
 *
 * Tier 1 is the customer answer, always visible when opened.
 * Tier 2 — "how this works" — is collapsed, and shows the request and response
 * that actually just happened, pulled live from the API call log. Not a
 * hardcoded example: the real thing, with the real latency.
 */
export default function InfoTip({ topic, callLabel, align = 'left' }) {
  const [open, setOpen] = useState(false)
  const [showDev, setShowDev] = useState(false)
  const ref = useRef(null)
  const doc = API_DOCS[topic]

  useEffect(() => {
    if (!open) return
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!doc) return null
  const call = callLabel ? getCall(callLabel) : null

  return (
    <span className="tip-wrap" ref={ref}>
      <button
        type="button"
        className="tip-btn"
        aria-expanded={open}
        aria-label="How this works"
        onClick={(e) => { e.stopPropagation(); e.preventDefault(); setOpen(!open) }}
      >i</button>

      {open && (
        <div className={`tip-pop ${align === 'right' ? 'right' : ''}`} role="dialog">
          <p className="tip-plain">{doc.plain}</p>

          <button type="button" className="tip-toggle" onClick={() => setShowDev(!showDev)}>
            {showDev ? '\u2013 Hide how this works' : '+ How this works'}
          </button>

          {showDev && (
            <div className="tip-dev">
              {doc.verb && (
                <dl>
                  <dt>Method</dt>
                  <dd><span className={`verb ${doc.verb === 'GET' ? 'get' : ''}`}>{doc.verb}</span> {doc.route}</dd>
                  {call && <><dt>Status</dt><dd>{call.status} \u00b7 {call.tookMs} ms</dd></>}
                  {call && <><dt>Called</dt><dd>{call.method} {call.url}</dd></>}
                </dl>
              )}

              <p className="tip-why">{doc.why}</p>

              {doc.layers?.length > 0 && (
                <dl style={{ marginTop: 12 }}>
                  {doc.layers.map(([k, v]) => (
                    <div key={k} style={{ display: 'contents' }}>
                      <dt>{k}</dt>
                      <dd style={{ fontFamily: 'var(--body)', fontSize: 12, wordBreak: 'normal' }}>{v}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {call?.requestBody && (
                <>
                  <div className="eyebrow" style={{ marginTop: 14 }}>What we sent</div>
                  <pre>{JSON.stringify(call.requestBody, null, 2)}</pre>
                </>
              )}
              {call?.responseBody && (
                <>
                  <div className="eyebrow" style={{ marginTop: 12 }}>What came back</div>
                  <pre>{summarise(call.responseBody)}</pre>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </span>
  )
}

/** Trim huge arrays so the panel stays readable rather than dumping 40 products. */
function summarise(body) {
  const clone = JSON.parse(JSON.stringify(body))
  const trim = (arr, keep = 1) => {
    if (!Array.isArray(arr)) return arr
    const head = arr.slice(0, keep).map((p) => ({
      ...p,
      ingredients: Array.isArray(p.ingredients) ? [...p.ingredients.slice(0, 4), `\u2026+${Math.max(0, p.ingredients.length - 4)} more`] : p.ingredients,
      search_text: undefined,
    }))
    return arr.length > keep ? [...head, `\u2026 ${arr.length - keep} more`] : head
  }
  if (clone.products) clone.products = trim(clone.products)
  if (clone.items) clone.items = trim(clone.items)
  if (clone.retrieved_products) clone.retrieved_products = trim(clone.retrieved_products)
  if (clone.brands?.length > 6) clone.brands = [...clone.brands.slice(0, 6), `\u2026 ${clone.brands.length - 6} more`]
  if (Array.isArray(clone.ingredients)) clone.ingredients = [...clone.ingredients.slice(0, 4), '\u2026']
  return JSON.stringify(clone, null, 2)
}
