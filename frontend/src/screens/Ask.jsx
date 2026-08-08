import { useState, useEffect, useRef } from 'react'
import { api, sessionId } from '../lib/api'
import { useStore } from '../App'
import ProductCard from '../components/ProductCard'
import InfoTip from '../components/InfoTip'

const STARTERS = [
  'What order should I apply things in?',
  "What's the difference between a serum and an essence?",
  'Can I use vitamin C and retinol together?',
]

/**
 * Chat is deliberately SECONDARY.
 *
 * A chat-first UI hides the option set, prevents comparison, produces no
 * structured preference data and costs money per turn. It's excellent at the
 * long tail of questions and poor at shortlisting — so it's scoped to what it's
 * good at, and every product it names is rendered as a real card rather than
 * left as prose the customer then has to go and find.
 */
export default function Ask() {
  const { toggleCompare, compare } = useStore()
  const [turns, setTurns] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    api.history(sessionId())
      .then((h) => setTurns((h.items || []).slice().reverse().map((i) => ({
        q: i.user_message, a: i.assistant_response, products: [], model: i.model,
      }))))
      .catch(() => {})
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, busy])

  const send = async (text) => {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput(''); setBusy(true)
    setTurns((t) => [...t, { q: message, a: null, products: [] }])
    try {
      const r = await api.chat({ message, session_id: sessionId(), top_k: 4 })
      setTurns((t) => t.map((turn, i) => i === t.length - 1
        ? { ...turn, a: r.answer, products: r.retrieved_products || [], model: r.model, safety: r.safety_redirect, low: r.low_confidence }
        : turn))
    } catch (e) {
      setTurns((t) => t.map((turn, i) => i === t.length - 1 ? { ...turn, a: e.message } : turn))
    }
    setBusy(false)
  }

  return (
    <div className="shell" style={{ paddingTop: 'var(--s6)', paddingBottom: 'var(--s9)', maxWidth: 820 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <div className="eyebrow">Ask a question</div>
        <InfoTip topic="chat" callLabel="chat" />
        <button className="linkbtn" style={{ marginLeft: 'auto' }}
          onClick={async () => { await api.clearHistory(sessionId()).catch(() => {}); setTurns([]) }}>
          Clear history
        </button>
        <InfoTip topic="history" callLabel="history" align="right" />
      </div>

      <p className="note" style={{ margin: '14px 0 28px' }}>
        General skincare information drawn from this catalogue. Not medical advice —
        anything about a skin condition, a prescription, or pregnancy goes to a
        professional rather than to the model.
      </p>

      {turns.length === 0 && (
        <div className="chip-row" style={{ marginBottom: 'var(--s6)' }}>
          {STARTERS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
        </div>
      )}

      <div className="thread">
        {turns.map((t, i) => (
          <div key={i} style={{ display: 'contents' }}>
            <div className="bubble user">{t.q}</div>
            {t.a === null
              ? <div className="bubble bot"><span className="spinner">THINKING\u2026</span></div>
              : <div className="bubble bot">
                  {t.a}
                  {t.model && (
                    <div className="eyebrow" style={{ marginTop: 12 }}>
                      {t.safety ? `SAFETY GATE \u2014 ${t.safety.toUpperCase()}`
                        : t.low ? 'BELOW CONFIDENCE FLOOR \u2014 NO MODEL CALLED'
                        : `VIA ${t.model.toUpperCase()}`}
                    </div>
                  )}
                </div>}
            {t.products?.length > 0 && (
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))' }}>
                {t.products.slice(0, 4).map((p) => (
                  <ProductCard key={p.id} product={p} onCompare={toggleCompare}
                    compared={!!compare.find((c) => c.id === p.id)} />
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send() }}
        style={{ display: 'flex', gap: 10, marginTop: 'var(--s6)' }}>
        <input className="textinput" value={input} maxLength={2000} disabled={busy}
          onChange={(e) => setInput(e.target.value)} placeholder="Ask about ingredients, routines, or layering\u2026" />
        <button className="btn" type="submit" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  )
}
