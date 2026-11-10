import { vi } from 'vitest'

type Handler = (body: unknown) => { status?: number; body?: unknown } | undefined
export type Routes = Record<string, Handler>

export const calls: { method: string; path: string; body: unknown }[] = []

/** Simula la API: claves "METHOD /ruta" (sin /api/v1). Rutas no definidas responden 404. */
export function mockApi(routes: Routes) {
  calls.length = 0
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.replace(/^.*\/api\/v1/, '').split('?')[0]
    const body = init?.body && typeof init.body === 'string' ? JSON.parse(init.body) : undefined
    calls.push({ method, path, body })
    const handler = routes[`${method} ${path}`]
    const result = handler ? handler(body) : { status: 404, body: { code: 'not_found', title: 'No encontrado' } }
    const status = result?.status ?? 200
    const isError = status >= 400
    if (status === 204) return new Response(null, { status })
    return new Response(JSON.stringify(result?.body ?? {}), {
      status,
      headers: { 'Content-Type': isError ? 'application/problem+json' : 'application/json' },
    })
  })
}

export const session = {
  access_token: 'tok',
  expires_in: 900,
  user: { id: 'u1', email: 'duena@demo.local', full_name: 'Dueña Demo', role: 'owner', is_active: true },
  pyme: { id: 'p1', name: 'Cocina Demo', default_margin_pct: '40.00', vat_pct: '19.00', is_demo: true },
}

export const recipes = [
  { id: 'r-pino', name: 'Empanadas de pino', yield_unit: 'unit', is_active: true },
  { id: 'r-queso', name: 'Empanadas de queso', yield_unit: 'unit', is_active: true },
  { id: 'r-sopa', name: 'Sopaipillas', yield_unit: 'unit', is_active: true },
]

export const incompleteQuote = {
  id: 'q1',
  order_id: 'o1',
  version: 1,
  status: 'draft',
  valid_until: '2026-11-24',
  vat_pct: '19.00',
  is_complete: false,
  missing_prices: ['Eneldo'],
  ingredients_cost_clp: 59738,
  net_clp: 83600,
  vat_clp: 15884,
  total_clp: 99484,
  shopping_total_clp: 2290,
  products: [
    { recipe_name: 'Empanadas de pino', qty: '80.000', unit_label: 'unidades', unit_price_clp: 1045, subtotal_clp: 83600 },
    { recipe_name: 'Canapés de salmón', qty: '60.000', unit_label: 'unidades', unit_price_clp: null, subtotal_clp: null },
  ],
}
