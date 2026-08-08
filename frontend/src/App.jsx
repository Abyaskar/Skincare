import { useState, createContext, useContext, useEffect } from 'react'
import { Routes, Route, Link, NavLink, useNavigate } from 'react-router-dom'
import Landing from './screens/Landing'
import Intake from './screens/Intake'
import Results from './screens/Results'
import ProductDetail from './screens/ProductDetail'
import Compare from './screens/Compare'
import Browse from './screens/Browse'
import Ask from './screens/Ask'
import { api } from './lib/api'

/** Shared state: the customer's answers, the last result set, compare picks. */
const Store = createContext(null)
export const useStore = () => useContext(Store)

export default function App() {
  const [intake, setIntake] = useState({
    concerns: [], text: '', skin_type: null, max_price: null, min_price: null,
    avoid: [], include: [], product_types: [],
  })
  const [result, setResult] = useState(null)
  const [compare, setCompare] = useState([])
  const [facets, setFacets] = useState(null)
  const navigate = useNavigate()

  useEffect(() => { api.facets().then(setFacets).catch(() => {}) }, [])

  const toggleCompare = (product) => {
    setCompare((cur) => {
      if (cur.find((p) => p.id === product.id)) return cur.filter((p) => p.id !== product.id)
      if (cur.length >= 3) return cur
      return [...cur, product]
    })
  }

  return (
    <Store.Provider value={{ intake, setIntake, result, setResult, compare, setCompare, toggleCompare, facets }}>
      <header className="site-header">
        <div className="inner">
          <Link to="/" className="wordmark">Formul<span>ary</span></Link>
          <NavLink to="/find" className="navlink">Find my skincare</NavLink>
          <NavLink to="/browse" className="navlink">Browse</NavLink>
          <NavLink to="/ask" className="navlink">Ask</NavLink>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/find" element={<Intake />} />
          <Route path="/results" element={<Results />} />
          <Route path="/product/:id" element={<ProductDetail />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/ask" element={<Ask />} />
        </Routes>
      </main>

      {compare.length >= 2 && (
        <div className="tray">
          <span style={{ fontFamily: 'var(--mono)', fontSize: 12, letterSpacing: '.08em' }}>
            {compare.length} SELECTED
          </span>
          <span style={{ marginRight: 'auto', fontSize: 13, opacity: .75 }}>
            {compare.map((p) => p.product_name).join('  \u00b7  ').slice(0, 70)}
          </span>
          <button className="linkbtn" style={{ color: 'var(--stone)' }} onClick={() => setCompare([])}>Clear</button>
          <button className="btn small" onClick={() => navigate('/compare')}>Compare</button>
        </div>
      )}

      <footer className="site-footer">
        <div className="shell">
          Product suggestions based on published ingredient lists. Not medical advice.
          For a skin condition, please see a pharmacist or dermatologist.
        </div>
      </footer>
    </Store.Provider>
  )
}
