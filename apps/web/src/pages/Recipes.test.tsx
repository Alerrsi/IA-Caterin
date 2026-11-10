import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session } from '../test/mockApi'

const list = [
  { id: 'r1', name: 'Empanadas de pino', yield_qty: '12.000', yield_unit: 'unit', is_final_product: true, vision_class: null, is_active: true, updated_at: 'x' },
  { id: 'r2', name: 'Pino (relleno)', yield_qty: '2000.000', yield_unit: 'g', is_final_product: false, vision_class: null, is_active: true, updated_at: 'x' },
]
const detail = {
  ...list[0],
  notes: null,
  version: 1,
  lines: [
    { id: 'l1', ingredient_id: 'i1', ingredient_name: 'Harina sin polvos', base_unit: 'g', qty: '500.000', waste_pct: null },
    { id: 'l2', ingredient_id: 'i2', ingredient_name: 'Eneldo', base_unit: 'g', qty: '10.000', waste_pct: null },
  ],
}
const cost = (qty: string) => ({
  recipe_id: 'r1',
  recipe_name: 'Empanadas de pino',
  units: qty,
  yield_unit: 'unit',
  total_clp: qty === '24' ? 18000 : 9000,
  per_unit_clp: 750,
  is_complete: false,
  missing_prices: ['Eneldo'],
  vat_included: true,
  lines: [
    { ingredient_id: 'i1', ingredient_name: 'Harina sin polvos', base_unit: 'g', required_qty: '500.000', waste_pct: '0', supplier_name: 'Harinas Cautín', package_label: 'saco 25 kg', price_date: '2026-11-01', price_id: 'p', unit_price_clp: '1', cost_clp: 9000 },
    { ingredient_id: 'i2', ingredient_name: 'Eneldo', base_unit: 'g', required_qty: '10.000', waste_pct: '0', supplier_name: null, package_label: null, price_date: null, price_id: null, unit_price_clp: null, cost_clp: null },
  ],
})

const routes = (role: 'owner' | 'collaborator') => ({
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role } } }),
  'GET /recipes': () => ({ body: list }),
  'GET /recipes/r1': () => ({ body: detail }),
  'GET /recipes/r1/cost': () => {
    const last = [...spyUrls].reverse().find((u) => u.includes('/cost'))!
    return { body: cost(new URL(last, 'http://x').searchParams.get('qty')!) }
  },
})
let spyUrls: string[] = []

function mock(role: 'owner' | 'collaborator') {
  const spy = mockApi(routes(role))
  const impl = spy.getMockImplementation()!
  spy.mockImplementation(async (input, init) => {
    spyUrls.push(String(input))
    return impl(input, init)
  })
}

beforeEach(() => {
  resetMemory()
  spyUrls = []
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

test('lista de recetas con rendimiento y búsqueda', async () => {
  window.location.hash = '#/recetas'
  mock('owner')
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText('Empanadas de pino')).toBeInTheDocument()
  expect(screen.getByText(/Rinde 2 kg/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Buscar receta'), 'pino (')
  expect(screen.queryByText('Empanadas de pino')).not.toBeInTheDocument()
  await user.click(screen.getByText('Pino (relleno)'))
  expect(window.location.hash).toBe('#/recetas/r2')
})

test('la dueña ve el costo con proveedor y el aviso de precios faltantes', async () => {
  window.location.hash = '#/recetas/r1'
  mock('owner')
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText('Harina sin polvos')).toBeInTheDocument()
  expect(await screen.findByTestId('recipe-cost-total')).toHaveTextContent('$9.000')
  expect(screen.getByText(/Falta el precio de: Eneldo/)).toBeInTheDocument()
  expect(screen.getByText('Harinas Cautín, precio del 01-11-2026')).toBeInTheDocument()
  const qty = screen.getByLabelText('Cantidad a producir')
  await user.clear(qty)
  await user.type(qty, '24')
  await user.click(screen.getByRole('button', { name: 'Calcular costo' }))
  expect(await screen.findByText('$18.000')).toBeInTheDocument()
})

test('la colaboradora ve los insumos pero no el costo', async () => {
  window.location.hash = '#/recetas/r1'
  mock('collaborator')
  render(<App />)
  expect(await screen.findByText('Harina sin polvos')).toBeInTheDocument()
  expect(screen.getByText('El costo lo ve la dueña.')).toBeInTheDocument()
  expect(calls.some((c) => c.path.endsWith('/cost'))).toBe(false)
})

test('sin señal el costo explica que necesita internet', async () => {
  window.location.hash = '#/recetas/r1'
  mock('owner')
  const first = render(<App />)
  await screen.findByText('Harina sin polvos')
  first.unmount()
  Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
  try {
    render(<App />)
    expect(await screen.findByText(/necesita internet/)).toBeInTheDocument()
    expect(screen.getByText('Harina sin polvos')).toBeInTheDocument()
  } finally {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  }
})
