/**
 * Mirror of the backend's avoidance groups, used only for HIGHLIGHTING in the
 * card ground.
 *
 * The authoritative version lives in the backend (app/utils/ingredient_intel.py)
 * and is what actually filters results. This copy never decides what a customer
 * sees — it only decides which words get picked out visually. Deciding safety in
 * two places would guarantee they eventually disagree.
 */
const GROUPS = {
  fragrance: ['parfum', 'fragrance', 'aroma', 'linalool', 'limonene', 'citronellol', 'geraniol', 'citral', 'eugenol', 'coumarin', 'benzyl salicylate'],
  'drying alcohol': ['alcohol denat', 'sd alcohol', 'ethanol', 'isopropyl alcohol'],
  'essential oils': ['lavandula', 'rosmarinus', 'mentha', 'eucalyptus', 'citrus aurantium', 'melaleuca', 'essential oil'],
  silicones: ['dimethicon', 'siloxane', 'silsesquioxane', 'dimethiconol'],
  sulfates: ['lauryl sulfate', 'laureth sulfate'],
  parabens: ['paraben'],
  'nut oils': ['prunus amygdalus', 'corylus avellana', 'macadamia', 'juglans', 'argania', 'anacardium'],
  coconut: ['cocos nucifera', 'coconut', 'cocamidopropyl', 'sodium cocoyl'],
  'shea butter': ['butyrospermum', 'shea'],
  'salicylic acid': ['salicylic acid', 'salix alba'],
  retinoids: ['retinol', 'retinal', 'retinyl', 'bakuchiol'],
  'exfoliating acids': ['glycolic acid', 'lactic acid', 'mandelic acid', 'salicylic acid', 'azelaic acid'],
  'mineral oil': ['paraffinum liquidum', 'mineral oil', 'petrolatum'],
  gluten: ['triticum vulgare', 'hordeum', 'avena sativa'],
}

const ALIASES = {
  perfume: 'fragrance', parfum: 'fragrance', scent: 'fragrance',
  alcohol: 'drying alcohol', 'alcohol denat': 'drying alcohol',
  silicone: 'silicones', dimethicone: 'silicones',
  sulfate: 'sulfates', sulphate: 'sulfates', paraben: 'parabens',
  nut: 'nut oils', nuts: 'nut oils', almond: 'nut oils',
  shea: 'shea butter', bha: 'salicylic acid', aha: 'exfoliating acids',
  retinol: 'retinoids', retinoid: 'retinoids', 'vitamin a': 'retinoids',
  petrolatum: 'mineral oil',
}

export function resolveAvoidTerms(term) {
  const key = ALIASES[(term || '').toLowerCase().trim()] || (term || '').toLowerCase().trim()
  return { label: key, patterns: GROUPS[key] || (key ? [key] : []) }
}

export const AVOID_GROUP_NAMES = Object.keys(GROUPS)
