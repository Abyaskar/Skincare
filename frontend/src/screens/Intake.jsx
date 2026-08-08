import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../App'
import InfoTip from '../components/InfoTip'
import { AVOID_GROUP_NAMES } from '../lib/avoid'

const CONCERNS = [
  ['dryness', 'Dryness or tightness'], ['oiliness', 'Oiliness or shine'],
  ['breakouts', 'Breakouts'], ['dullness', 'Dullness'],
  ['dark spots', 'Dark spots'], ['fine lines', 'Fine lines'],
  ['redness', 'Redness or sensitivity'], ['sun protection', 'Sun protection'],
  ['daily routine', 'Just building a routine'],
]
const SKIN = ['oily', 'dry', 'combination', 'sensitive', 'normal']
const BUDGETS = [['Under \u00a310', 10], ['Under \u00a325', 25], ['Under \u00a350', 50], ['No limit', null]]
const QUICK_AVOID = ['fragrance', 'drying alcohol', 'essential oils', 'silicones', 'nut oils', 'parabens']

/**
 * Four steps, every one skippable after the first. The drop-off curve punishes
 * a fifth question, and each answered step converts a soft semantic guess into
 * a hard deterministic filter — which is what makes results feel picked rather
 * than searched.
 *
 * All four are collected client-side and submitted as ONE /recommend call.
 * Calling the API per step would waste compute and fill the logs with
 * half-formed queries.
 */
export default function Intake() {
  const { intake, setIntake, facets } = useStore()
  const [step, setStep] = useState(1)
  const navigate = useNavigate()
  const set = (patch) => setIntake({ ...intake, ...patch })

  const toggle = (key, value) => {
    const cur = intake[key]
    set({ [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] })
  }

  const canContinue = step > 1 || intake.concerns.length > 0 || intake.text.trim().length > 0
  const types = facets?.product_types || []
  const avoidOptions = facets?.avoid_groups?.length ? facets.avoid_groups : AVOID_GROUP_NAMES

  return (
    <div className="shell" style={{ paddingTop: 'var(--s8)', paddingBottom: 'var(--s9)', maxWidth: 760 }}>
      <div className="progress">
        {[1, 2, 3, 4].map((i) => <i key={i} className={i <= step ? 'done' : ''} />)}
      </div>
      <div className="eyebrow">Step {step} of 4</div>

      {step === 1 && (
        <>
          <div className="field-label" style={{ marginTop: 16 }}>What's your skin doing?</div>
          <p className="field-help">Pick what applies, or describe it in your own words. One or the other is enough.</p>
          <div className="chip-row">
            {CONCERNS.map(([v, label]) => (
              <button key={v} className="chip" aria-pressed={intake.concerns.includes(v)}
                onClick={() => toggle('concerns', v)}>{label}</button>
            ))}
          </div>
          <input className="textinput" style={{ marginTop: 'var(--s5)' }} maxLength={500}
            placeholder="e.g. dry patches on my cheeks, fragrance makes me itch"
            value={intake.text} onChange={(e) => set({ text: e.target.value })} />
        </>
      )}

      {step === 2 && (
        <>
          <div className="field-label" style={{ marginTop: 16 }}>
            How would you describe your skin type? <InfoTip topic="derived" />
          </div>
          <p className="field-help">
            Optional. We'll prioritise products often suited to it — worked out from
            ingredients, since brands don't publish this in a standard way.
          </p>
          <div className="chip-row">
            <button className="chip" aria-pressed={!intake.skin_type} onClick={() => set({ skin_type: null })}>Not sure</button>
            {SKIN.map((s) => (
              <button key={s} className="chip" aria-pressed={intake.skin_type === s}
                onClick={() => set({ skin_type: s })} style={{ textTransform: 'capitalize' }}>{s}</button>
            ))}
          </div>
        </>
      )}

      {step === 3 && (
        <>
          <div className="field-label" style={{ marginTop: 16 }}>Anything you need to avoid?</div>
          <p className="field-help">
            This is the one that matters most. We match the ingredient names as they
            appear on each product's list — always check the label yourself if you have an allergy.
          </p>
          <div className="chip-row">
            {avoidOptions.filter((a) => QUICK_AVOID.includes(a) || avoidOptions.length <= 8).map((a) => (
              <button key={a} className="chip avoid" aria-pressed={intake.avoid.includes(a)}
                onClick={() => toggle('avoid', a)}>{a}</button>
            ))}
          </div>
          <div className="field-label" style={{ fontSize: '1.1rem', marginTop: 'var(--s6)' }}>Budget</div>
          <div className="chip-row" style={{ marginTop: 10 }}>
            {BUDGETS.map(([label, v]) => (
              <button key={label} className="chip" aria-pressed={intake.max_price === v}
                onClick={() => set({ max_price: v })}>{label}</button>
            ))}
          </div>
        </>
      )}

      {step === 4 && (
        <>
          <div className="field-label" style={{ marginTop: 16 }}>What are you looking for?</div>
          <p className="field-help">Optional. Leave it open and we'll suggest across categories.</p>
          <div className="chip-row">
            {types.map((t) => (
              <button key={t} className="chip" aria-pressed={intake.product_types.includes(t)}
                onClick={() => toggle('product_types', t)}>{t}</button>
            ))}
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: 'var(--s3)', alignItems: 'center', marginTop: 'var(--s7)' }}>
        {step > 1 && <button className="btn ghost" onClick={() => setStep(step - 1)}>Back</button>}
        {step < 4 ? (
          <>
            <button className="btn" disabled={!canContinue} onClick={() => setStep(step + 1)}>Continue</button>
            {step > 1 && <button className="linkbtn" onClick={() => setStep(step + 1)}>Skip</button>}
            <button className="linkbtn" style={{ marginLeft: 'auto' }} onClick={() => navigate('/results')}>
              Skip the rest, show matches
            </button>
          </>
        ) : (
          <button className="btn" onClick={() => navigate('/results')}>See my matches</button>
        )}
      </div>

      <p className="note" style={{ marginTop: 'var(--s7)' }}>
        We use these answers to find products. We don't diagnose skin conditions, and
        nothing here is stored against your identity.
      </p>
    </div>
  )
}
