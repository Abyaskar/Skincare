import { Link } from 'react-router-dom'
import { useStore } from '../App'
import InfoTip from '../components/InfoTip'

export default function Landing() {
  const { facets } = useStore()
  const n = facets?.total_products

  return (
    <div className="shell" style={{ paddingTop: 'var(--s9)', paddingBottom: 'var(--s8)' }}>
      <div style={{ maxWidth: 720 }}>
        <div className="eyebrow">Skincare, matched by ingredient</div>
        <h1 style={{ marginTop: 'var(--s4)' }}>
          Every product here is<br />
          <em style={{ fontStyle: 'italic', color: 'var(--pine)' }}>an ingredient list</em><br />
          before it's a promise.
        </h1>
        <p style={{ marginTop: 'var(--s5)', fontSize: '1.05rem', maxWidth: 560, color: 'var(--ink-soft)' }}>
          Tell us what your skin is doing and what you can't use. We'll check
          {n ? ` all ${n.toLocaleString()} products` : ' the whole catalogue'} against
          your rules and show you a short list — with the reasoning attached to each one.
        </p>

        <div style={{ display: 'flex', gap: 'var(--s3)', flexWrap: 'wrap', marginTop: 'var(--s6)' }}>
          <Link to="/find" className="btn">Find my skincare</Link>
          <Link to="/browse" className="btn ghost">Browse everything</Link>
        </div>
      </div>

      <hr className="rule" style={{ marginTop: 'var(--s9)' }} />

      <div style={{ display: 'grid', gap: 'var(--s6)', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
        <div>
          <div className="eyebrow">01 — Rules, not vibes</div>
          <p style={{ marginTop: 10 }}>
            Say "no fragrance" and we match it against parfum, linalool, limonene and
            the rest — not just the word "fragrance", which almost no label uses.
            <InfoTip topic="recommend" />
          </p>
        </div>
        <div>
          <div className="eyebrow">02 — Shown, not claimed</div>
          <p style={{ marginTop: 10 }}>
            The pattern on each product is its real ingredient list, with your
            matches picked out. You can check our reasoning rather than trust it.
            <InfoTip topic="ground" />
          </p>
        </div>
        <div>
          <div className="eyebrow">03 — Allowed to say no</div>
          <p style={{ marginTop: 10 }}>
            If nothing in the catalogue genuinely fits, we say so and offer to
            loosen one rule — rather than quietly showing you the least-bad option.
          </p>
        </div>
      </div>
    </div>
  )
}
