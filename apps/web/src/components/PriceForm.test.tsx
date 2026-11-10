import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session } from '../test/mockApi'

const harina = {
  id: 'i1', name: 'Harina sin polvos', base_unit: 'g', stock_qty: '18000.000', min_stock_qty: null, waste_pct: null,
  category: null, is_active: true, is_low: false, updated_at: 'x',
}
const price = {
  price_id: 'p1', supplier_id: 's1', supplier_name: 'Molino Sur', package_label: 'saco 25 kg', package_qty: '25000.000',
  price_clp: 21000, includes_vat: true, price_date: '2026-11-09', gross_price_clp: '21000', price_per_base_unit_clp: '0.84',
  price_per_reference_clp: '840', reference_unit: 'kg', is_best: true,
}

function routes(suppliers: unknown[]) {
  let saved = false
  return {
    'POST /auth/refresh': () => ({ body: session }),
    'GET /ingredients': () => ({ body: { items: [harina], next_cursor: null } }),
    'GET /ingredients/i1/movements': () => ({ body: { items: [], next_cursor: null } }),
    'GET /ingredients/i1/prices': () => ({ body: { ingredient_id: 'i1', ingredient_name: 'Harina sin polvos', base_unit: 'g', items: saved ? [price] : [] } }),
    'GET /suppliers': () => ({ body: suppliers }),
    'POST /suppliers': () => ({ status: 201, body: { id: 's-new', name: 'Molino Sur', is_active: true } }),
    'POST /prices': () => {
      saved = true
      return { status: 201, body: { id: 'p1' } }
    },
  }
}

beforeEach(() => {
  resetMemory()
  window.location.hash = '#/inventario/i1'
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

test('sin proveedores: crea el proveedor y el precio, y lo muestra como vigente', async () => {
  mockApi(routes([]))
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText(/Todavía no tiene precio/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Agregar precio' }))
  await user.type(await screen.findByLabelText('Nombre del proveedor nuevo'), 'Molino Sur')
  await user.type(screen.getByLabelText('Presentación'), 'saco 25 kg')
  await user.type(screen.getByLabelText('Cantidad que trae'), '25')
  expect(screen.getByLabelText('Unidad')).toHaveValue('kg')
  await user.type(screen.getByLabelText('Precio en pesos'), '$21.000')
  await user.click(screen.getByRole('button', { name: 'Guardar precio' }))
  expect(await screen.findByText('Precio guardado.')).toBeInTheDocument()
  expect(await screen.findByText(/saco 25 kg: \$21\.000/)).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/suppliers' && c.method === 'POST')?.body).toEqual({ name: 'Molino Sur' })
  const body = calls.find((c) => c.path === '/prices' && c.method === 'POST')?.body as Record<string, unknown>
  expect(body).toMatchObject({
    ingredient_id: 'i1', supplier_id: 's-new', package_label: 'saco 25 kg', package_qty: '25', package_unit: 'kg',
    price_clp: 21000, includes_vat: true,
  })
  expect(body.price_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
})

test('con proveedor existente no crea otro, y valida el precio', async () => {
  mockApi(routes([{ id: 's1', name: 'Molino Sur', is_active: true }]))
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Agregar precio' }))
  await user.click(await screen.findByRole('button', { name: 'Guardar precio' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Elige un proveedor')
  await user.selectOptions(screen.getByLabelText('Proveedor'), 's1')
  await user.type(screen.getByLabelText('Presentación'), 'bolsa 1 kg')
  await user.type(screen.getByLabelText('Cantidad que trae'), '1')
  await user.type(screen.getByLabelText('Precio en pesos'), 'mil')
  await user.click(screen.getByRole('button', { name: 'Guardar precio' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Escribe un precio mayor que cero')
  await user.clear(screen.getByLabelText('Precio en pesos'))
  await user.type(screen.getByLabelText('Precio en pesos'), '1.290')
  await user.click(screen.getByRole('button', { name: 'Guardar precio' }))
  expect(await screen.findByText('Precio guardado.')).toBeInTheDocument()
  expect(calls.some((c) => c.path === '/suppliers' && c.method === 'POST')).toBe(false)
  expect(calls.find((c) => c.path === '/prices')?.body).toMatchObject({ supplier_id: 's1', price_clp: 1290 })
})
