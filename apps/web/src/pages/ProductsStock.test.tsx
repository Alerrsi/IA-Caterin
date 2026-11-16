import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session, type Routes } from '../test/mockApi'

const products = [
  { recipe_id: 'r-pino', name: 'Empanadas de pino', yield_unit: 'unit', stock_qty: '48.000', vision_class: 'empanada', updated_at: '2026-11-16T12:00:00Z' },
  { recipe_id: 'r-can', name: 'Canapés de salmón', yield_unit: 'unit', stock_qty: '-4.000', vision_class: null, updated_at: '2026-11-16T12:00:00Z' },
]

const productions = {
  items: [
    {
      id: 'pr1',
      recipe_id: 'r-pino',
      recipe_name: 'Empanadas de pino',
      detected_qty: 46,
      confirmed_qty: 48,
      model_version: 'fake-1',
      was_corrected: true,
      consumed_ingredients: true,
      voided_at: null,
      created_at: '2026-11-16T12:00:00Z',
      product_stock_qty: null,
      consumed: [],
    },
  ],
  next_cursor: null,
}

const routes = (role = 'owner'): Routes => ({
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role } } }),
  'GET /products/stock': () => ({ body: products }),
  'GET /vision/productions': () => ({ body: productions }),
  'GET /products/r-pino/movements': () => ({
    body: {
      items: [
        { id: 'm2', recipe_id: 'r-pino', delta_qty: '-12.000', reason: 'delivery', note: 'Pedido entregado', reference_type: 'order', reference_id: 'o1', occurred_at: '2026-11-16T15:00:00Z', created_at: '2026-11-16T15:00:00Z' },
        { id: 'm1', recipe_id: 'r-pino', delta_qty: '60.000', reason: 'production', note: 'Producción', reference_type: 'production', reference_id: 'pr1', occurred_at: '2026-11-16T12:00:00Z', created_at: '2026-11-16T12:00:00Z' },
      ],
      next_cursor: null,
    },
  }),
  'POST /products/movements': () => ({ status: 201, body: {} }),
  'POST /vision/productions/pr1/void': () => ({ body: { ...productions.items[0], voided_at: '2026-11-16T16:00:00Z' } }),
})

beforeEach(() => {
  window.location.hash = '#/inventario/productos'
  setAccessToken(null)
  resetMemory()
})
afterEach(() => vi.restoreAllMocks())

test('la dueña ve sus productos listos, ajusta una merma y anula una producción', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  const list = await screen.findByRole('list', { name: 'Productos listos' })
  expect(screen.getByRole('link', { name: 'Productos listos' })).toHaveAttribute('aria-current', 'page')
  const pino = within(list).getByText('Empanadas de pino').closest('li')!
  expect(within(pino).getByText('48 unid.')).toBeInTheDocument()
  const can = within(list).getByText('Canapés de salmón').closest('li')!
  expect(within(can).getByText('Quedó en negativo: revisa el conteo.')).toBeInTheDocument()

  // historial con motivos en palabras
  await user.click(within(pino).getByRole('button', { name: 'Ver movimientos' }))
  expect(await within(pino).findByText('Producción', { selector: 'li > span' })).toBeInTheDocument()
  expect(within(pino).getAllByText('Pedido entregado').length).toBeGreaterThan(0)
  expect(within(pino).getByText('−12 unid.')).toBeInTheDocument()

  // merma: siempre resta, va por la cola con clave de idempotencia
  await user.click(within(pino).getByRole('button', { name: 'Ajustar' }))
  await user.selectOptions(within(pino).getByLabelText('Motivo'), 'waste')
  await user.type(within(pino).getByLabelText('Cantidad'), '6')
  await user.click(within(pino).getByRole('button', { name: 'Guardar ajuste' }))
  await waitFor(() =>
    expect(calls.find((c) => c.path === '/products/movements')?.body).toEqual({
      recipe_id: 'r-pino',
      reason: 'waste',
      delta_qty: '-6',
      note: null,
    }),
  )
  expect(within(pino).getByText('42 unid.')).toBeInTheDocument()

  // anular pide confirmación
  const recent = screen.getByRole('region', { name: 'Producción reciente' })
  expect(within(recent).getByText(/corregida \(la foto contó 46\)/)).toBeInTheDocument()
  await user.click(within(recent).getByRole('button', { name: 'Anular' }))
  expect(calls.some((c) => c.path === '/vision/productions/pr1/void')).toBe(false)
  await user.click(within(recent).getByRole('button', { name: 'Sí, anular' }))
  expect(await screen.findByText(/Producción anulada/)).toBeInTheDocument()
  expect(calls.some((c) => c.method === 'POST' && c.path === '/vision/productions/pr1/void')).toBe(true)
})

test('la colaboradora ajusta pero no puede anular producciones', async () => {
  mockApi(routes('collaborator'))
  render(<App />)
  const recent = await screen.findByRole('region', { name: 'Producción reciente' })
  expect(await within(recent).findByText('Empanadas de pino')).toBeInTheDocument()
  expect(within(recent).queryByRole('button', { name: 'Anular' })).not.toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Ajustar' })).toHaveLength(2)
})
