/**
 * API client.
 *
 * Every call is recorded into a small in-memory log keyed by a label. That log
 * is what the ⓘ tooltips read from, so the technical tier of a tooltip shows
 * the request and response that ACTUALLY just happened rather than a hardcoded
 * example. It's the difference between an architecture diagram and a live
 * window onto the running system.
 */

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const log = new Map()
const listeners = new Set()

export function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
export function getCall(label) {
  return log.get(label)
}

function record(label, entry) {
  log.set(label, entry)
  listeners.forEach((fn) => fn(label, entry))
}

async function request(label, method, path, { body, params } = {}) {
  const url = new URL(BASE + path)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }
  const started = performance.now()
  const init = { method, headers: { 'Content-Type': 'application/json' } }
  if (body !== undefined) init.body = JSON.stringify(body)

  let response, data, error = null
  try {
    response = await fetch(url.toString(), init)
    data = await response.json().catch(() => null)
    if (!response.ok) error = data?.message || `${response.status} ${response.statusText}`
  } catch (e) {
    error = `Could not reach the API at ${BASE}. Is the backend running?`
  }
  const tookMs = Math.round(performance.now() - started)

  record(label, {
    method,
    url: url.pathname + url.search,
    requestBody: body ?? null,
    status: response?.status ?? 0,
    responseBody: data,
    tookMs,
    at: new Date().toISOString(),
  })

  if (error) throw new Error(error)
  return data
}

export const api = {
  health:      ()    => request('health',    'GET',    '/health'),
  facets:      ()    => request('facets',    'GET',    '/products/facets'),
  products:    (p)   => request('products',  'GET',    '/products', { params: p }),
  product:     (id)  => request('product',   'GET',    `/products/${id}`),
  batch:       (ids) => request('batch',     'POST',   '/products/batch', { body: { product_ids: ids } }),
  recommend:   (b)   => request('recommend', 'POST',   '/recommend', { body: b }),
  similar:     (id)  => request('similar',   'POST',   '/recommend', { body: { strategy: 'content', product_id: id, top_k: 4 } }),
  search:      (b)   => request('search',    'POST',   '/search', { body: b }),
  chat:        (b)   => request('chat',      'POST',   '/chat', { body: b }),
  history:     (sid) => request('history',   'GET',    '/history', { params: { session_id: sid } }),
  clearHistory:(sid) => request('history',   'DELETE', '/history', { params: { session_id: sid } }),
  feedback:    (b)   => request('feedback',  'POST',   '/feedback', { body: b }),
}

/** Stable per-tab session id. Only ever used to scope this browser's own data. */
export function sessionId() {
  if (!window.__formularySession) {
    window.__formularySession =
      'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
  }
  return window.__formularySession
}
