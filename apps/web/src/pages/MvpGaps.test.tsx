import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, incompleteQuote, mockApi, recipes, session } from '../test/mockApi'

const loggedIn = { 'POST /auth/refresh': () => ({ body: session }) }
const collaborator = {
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role: 'collaborator' } } }),
}
const noMargin = { status: 422, body: { code: 'margin_required', title: 'Falta tu margen de ganancia' } }

const ingredient = (id: string, name: string) => ({
  id,
  name,
  base_unit: 'g',
  stock_qty: '0.000',
  min_stock_qty: null,
  waste_pct: null,
  category: null,
  is_active: true,
  is_low: false,
  updated_at: '2026-11-09T12:00:00Z',
})

const order = {
  id: 'o1',
  customer_name: 'Cliente demo',
  event_date: '2026-11-14',
  guests: 20,
  status: 'draft',
  lines: [{ id: 'l1', recipe_name: 'Sopaipillas', requested_name: 'Sopaipillas', qty: '24.000', unit: 'unit' }],
  last_quote_id: null,
}

beforeEach(() => {
  resetMemory()
  window.location.hash = ''
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

// --------------------------------------------------------------------------- nuevo insumo

test('crea un insumo convirtiendo a la unidad base y abre su detalle', async () => {
  window.location.hash = '#/inventario'
  const created = ingredient('i-new', 'Harina sin polvos')
  let list = [ingredient('i-sal', 'Sal')]
  mockApi({
    ...loggedIn,
    'GET /ingredients': () => ({ body: { items: list, next_cursor: null } }),
    'GET /prices': () => ({ body: [] }),
    'POST /ingredients': () => {
      list = [...list, { ...created, stock_qty: '2500.000' }]
      return { status: 201, body: { ...created, stock_qty: '2500.000' } }
    },
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Nuevo insumo' }))
  await user.type(await screen.findByLabelText('Nombre del insumo'), ' Harina sin polvos ')
  await user.type(screen.getByLabelText('Cuánto tienes ahora'), '2,5')
  await user.type(screen.getByLabelText(/Avisarme cuando quede menos/), '1')
  await user.type(screen.getByLabelText(/^Merma/), '3')
  await user.click(screen.getByRole('button', { name: 'Guardar insumo' }))
  await waitFor(() => expect(window.location.hash).toBe('#/inventario/i-new'))
  expect(calls.find((c) => c.path === '/ingredients' && c.method === 'POST')?.body).toEqual({
    name: 'Harina sin polvos',
    base_unit: 'g',
    initial_stock: '2500.000',
    min_stock_qty: '1000.000',
    waste_pct: '3',
    category: null,
  })
  expect(await screen.findByRole('heading', { name: 'Harina sin polvos' })).toBeInTheDocument()
})

test('nuevo insumo por unidad usa docenas y valida los datos', async () => {
  window.location.hash = '#/inventario/nuevo'
  mockApi({
    ...loggedIn,
    'GET /ingredients': () => ({ body: { items: [], next_cursor: null } }),
    'POST /ingredients': () => ({ status: 201, body: ingredient('i-h', 'Huevo') }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Guardar insumo' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Escribe el nombre del insumo')
  await user.type(screen.getByLabelText('Nombre del insumo'), 'Huevo')
  await user.click(screen.getByLabelText('Por unidad'))
  await user.selectOptions(screen.getByLabelText('Unidad'), 'docena')
  await user.type(screen.getByLabelText('Cuánto tienes ahora'), '-1')
  await user.click(screen.getByRole('button', { name: 'Guardar insumo' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Revisa las cantidades')
  await user.clear(screen.getByLabelText('Cuánto tienes ahora'))
  await user.type(screen.getByLabelText('Cuánto tienes ahora'), '2')
  await user.click(screen.getByRole('button', { name: 'Guardar insumo' }))
  await waitFor(() =>
    expect(calls.find((c) => c.path === '/ingredients' && c.method === 'POST')?.body).toMatchObject({
      base_unit: 'unit',
      initial_stock: '24.000',
      min_stock_qty: null,
    }),
  )
})

test('filtro "sin precio" en el inventario', async () => {
  window.location.hash = '#/inventario'
  mockApi({
    ...loggedIn,
    'GET /ingredients': () => ({
      body: { items: [ingredient('i-sal', 'Sal'), ingredient('i-har', 'Harina')], next_cursor: null },
    }),
    'GET /prices': () => ({ body: [{ ingredient_id: 'i-sal' }] }),
  })
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText('Sin precio')).toBeInTheDocument() // la insignia de Harina
  await user.click(await screen.findByLabelText('Solo los que no tienen precio'))
  expect(screen.queryByText('Sal')).not.toBeInTheDocument()
  expect(screen.getByText('Harina')).toBeInTheDocument()
})

// --------------------------------------------------------------------------- margen faltante

test('registro con margen opcional lo guarda en la pyme', async () => {
  window.location.hash = '#/registro'
  mockApi({
    'POST /auth/refresh': () => ({ status: 401, body: { code: 'unauthorized', title: 'x' } }),
    'POST /auth/register': () => ({ status: 201, body: session }),
    'PATCH /pyme': () => ({ body: {} }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Nombre de tu pyme'), 'Cocina Nueva')
  await user.type(screen.getByLabelText('Tu nombre'), 'Marta Soto')
  await user.type(screen.getByLabelText('Correo'), 'marta@demo.local')
  await user.type(screen.getByLabelText(/^Contraseña/), 'clave-segura-123')
  await user.type(screen.getByLabelText(/^Margen de ganancia/), '150')
  await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Revisa el margen')
  expect(calls.find((c) => c.path === '/auth/register')).toBeUndefined()
  await user.clear(screen.getByLabelText(/^Margen de ganancia/))
  await user.type(screen.getByLabelText(/^Margen de ganancia/), '35,5')
  await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))
  await waitFor(() => expect(calls.find((c) => c.path === '/pyme')?.body).toEqual({ default_margin_pct: '35.5' }))
})

test('sin margen: cotizar un pedido guardado pide el margen y reintenta con un toque', async () => {
  window.location.hash = '#/pedidos'
  let margin = false
  mockApi({
    ...loggedIn,
    'GET /orders': () => ({ body: [order] }),
    'PATCH /pyme': () => {
      margin = true
      return { body: {} }
    },
    'POST /orders/o1/quotes': () => (margin ? { status: 201, body: { ...incompleteQuote, id: 'q7' } } : noMargin),
    'GET /quotes/q7': () => ({ body: { ...incompleteQuote, id: 'q7' } }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Cotizar' }))
  expect(await screen.findByText('Falta tu margen de ganancia')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Guardar y cotizar' })).toBeDisabled() // sin valor sugerido
  await user.type(screen.getByLabelText('Margen de ganancia (%)'), '120')
  await user.click(screen.getByRole('button', { name: 'Guardar y cotizar' }))
  expect(await screen.findByText(/número entre 0 y 100/)).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/pyme')).toBeUndefined()
  await user.clear(screen.getByLabelText('Margen de ganancia (%)'))
  await user.type(screen.getByLabelText('Margen de ganancia (%)'), '40')
  await user.click(screen.getByRole('button', { name: 'Guardar y cotizar' }))
  await waitFor(() => expect(window.location.hash).toBe('#/cotizaciones/q7'))
  expect(calls.find((c) => c.path === '/pyme')?.body).toEqual({ default_margin_pct: '40' })
})

test('sin margen al cotizar un pedido nuevo: no se duplica el pedido al reintentar', async () => {
  window.location.hash = '#/cotizar'
  let margin = false
  mockApi({
    ...loggedIn,
    'GET /recipes': () => ({ body: recipes }),
    'POST /orders': () => ({ status: 201, body: { ...order, id: 'o9' } }),
    'PATCH /pyme': () => {
      margin = true
      return { body: {} }
    },
    'POST /orders/o9/quotes': () => (margin ? { status: 201, body: { ...incompleteQuote, id: 'q9' } } : noMargin),
    'GET /quotes/q9': () => ({ body: { ...incompleteQuote, id: 'q9' } }),
    'POST /metrics/quote-timing': () => ({ status: 201, body: {} }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Ingresar a mano' }))
  await user.type(screen.getByLabelText('Nombre del cliente'), 'Cliente demo')
  await user.selectOptions(screen.getByLabelText('Receta 1'), 'r-sopa')
  await user.type(screen.getByLabelText('Cantidad'), '24')
  await user.click(screen.getByRole('button', { name: 'Calcular cotización' }))
  await user.type(await screen.findByLabelText('Margen de ganancia (%)'), '40')
  await user.click(screen.getByRole('button', { name: 'Guardar y cotizar' }))
  await waitFor(() => expect(window.location.hash).toBe('#/cotizaciones/q9'))
  expect(calls.filter((c) => c.path === '/orders' && c.method === 'POST')).toHaveLength(1)
})

test('la colaboradora no puede fijar el margen: se le explica', async () => {
  window.location.hash = '#/pedidos'
  mockApi({ ...collaborator, 'GET /orders': () => ({ body: [order] }), 'POST /orders/o1/quotes': () => noMargin })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Cotizar' }))
  expect(await screen.findByText(/pídele a la dueña/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Guardar y cotizar' })).not.toBeInTheDocument()
})

// --------------------------------------------------------------------------- insumos sin precio

test('la cotización incompleta enlaza cada insumo sin precio a su detalle', async () => {
  window.location.hash = '#/cotizaciones/q1'
  mockApi({
    ...loggedIn,
    'GET /quotes/q1': () => ({ body: incompleteQuote }), // missing_prices: ['Eneldo']
    'GET /ingredients': () => ({ body: { items: [ingredient('i-eneldo', 'Eneldo')], next_cursor: null } }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Agregar precio de Eneldo' }))
  expect(window.location.hash).toBe('#/inventario/i-eneldo')
})
