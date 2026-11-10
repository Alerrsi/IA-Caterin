import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'
import { setAccessToken } from '../../api'
import { calls, mockApi, session } from '../../test/mockApi'

const customerSession = {
  ...session,
  user: { id: 'c1', email: 'ana@cliente.local', full_name: 'Ana Cliente', role: 'customer', is_active: true },
  pyme: { id: 'p1', name: 'Cocina Demo', commune: 'Temuco', vat_pct: '19.00', is_demo: true },
}
const anonymous = () => ({ status: 401, body: { code: 'unauthorized', title: 'Necesitas iniciar sesión' } })

const pymes = [
  { id: 'p1', name: 'Cocina Demo', commune: 'Temuco', joined: true },
  { id: 'p2', name: 'Banquetería Lago', commune: 'Villarrica', joined: false },
]

const draft = {
  id: 'o9',
  pyme_id: 'p1',
  pyme_name: 'Cocina Demo',
  status: 'customer_draft',
  created_at: '2026-11-10T12:00:00Z',
  submitted_at: null,
  decided_at: null,
  event_date: '2026-11-21',
  guests: 40,
  notes: null,
  owner_message: null,
  lines: [{ name: 'Empanadas de pino', qty: '5', unit: 'dozen', unit_label: 'docenas' }],
  quote: {
    version: 1,
    is_complete: true,
    products: [{ name: 'Empanadas de pino', qty: '5', unit_label: 'docenas', unit_price_clp: 12545, subtotal_clp: 62725 }],
    net_clp: 62725,
    vat_pct: '19',
    vat_clp: 11918,
    total_clp: 74643,
    valid_until: null,
  },
  price_pending: null,
  can_send: true,
  can_cancel: true,
}

beforeEach(() => setAccessToken(null))
afterEach(() => vi.restoreAllMocks())

test('un cliente se registra con el enlace de la pyme', async () => {
  window.location.hash = '#/cliente/abc123xyz'
  mockApi({
    'POST /auth/refresh': anonymous,
    'GET /portal/pymes/abc123xyz': () => ({ body: { name: 'Cocina Demo', commune: 'Temuco' } }),
    'POST /portal/register': () => ({ status: 201, body: customerSession }),
    'GET /portal/requests': () => ({ body: [] }),
  })
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText('Para cotizar tus pedidos con Cocina Demo.')).toBeInTheDocument()
  await user.type(screen.getByLabelText('Tu nombre'), 'Ana Cliente')
  await user.type(screen.getByLabelText('Correo'), 'ana@cliente.local')
  await user.type(screen.getByLabelText(/^Contraseña/), 'clave-segura-123')
  await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))
  expect(await screen.findByRole('heading', { name: 'Mis cotizaciones' })).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/portal/register')?.body).toEqual({
    code: 'abc123xyz',
    full_name: 'Ana Cliente',
    email: 'ana@cliente.local',
    password: 'clave-segura-123',
  })
})

test('un enlace inválido lo dice', async () => {
  window.location.hash = '#/cliente/malo'
  mockApi({ 'POST /auth/refresh': anonymous })
  render(<App />)
  expect(await screen.findByText(/Este enlace no es válido/)).toBeInTheDocument()
})

test('el cliente cotiza con el formulario y guarda sin enviar', async () => {
  window.location.hash = '#/cotizar'
  mockApi({
    'POST /auth/refresh': () => ({ body: customerSession }),
    'GET /portal/pymes': () => ({ body: pymes }),
    'GET /portal/products': () => ({ body: [{ id: 'r-pino', name: 'Empanadas de pino', yield_unit: 'unit' }] }),
    'POST /portal/requests': () => ({ status: 201, body: draft }),
    'GET /portal/requests/o9': () => ({ body: draft }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Ingresar a mano' }))
  expect(screen.queryByLabelText('Nombre del cliente')).not.toBeInTheDocument() // es su cuenta
  await user.selectOptions(await screen.findByLabelText('Producto 1'), 'r-pino')
  await user.type(screen.getByLabelText('Cantidad'), '5')
  await user.selectOptions(screen.getByLabelText('Unidad'), 'dozen')
  await user.type(screen.getByLabelText(/Comentarios para la pyme/), 'sin cebolla')
  await user.click(screen.getByRole('button', { name: 'Ver precio y guardar' }))
  expect(await screen.findByTestId('request-total')).toHaveTextContent('$74.643')
  expect(calls.find((c) => c.path === '/portal/requests' && c.method === 'POST')?.body).toMatchObject({
    pyme_id: 'p1',
    notes: 'sin cebolla',
    source: 'form',
    lines: [{ recipe_id: 'r-pino', qty: '5', unit: 'dozen' }],
  })
  expect(calls.some((c) => c.path === '/orders' || c.path === '/recipes')).toBe(false)
})

test('el cliente envía su cotización guardada a la pyme', async () => {
  window.location.hash = '#/solicitudes/o9'
  mockApi({
    'POST /auth/refresh': () => ({ body: customerSession }),
    'GET /portal/requests/o9': () => ({ body: draft }),
    'POST /portal/requests/o9/send': () => ({
      body: { ...draft, status: 'requested', submitted_at: '2026-11-10T13:00:00Z', can_send: false },
    }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Enviar a Cocina Demo' }))
  expect(await screen.findByText('Enviada, esperando respuesta')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Enviar a Cocina Demo' })).not.toBeInTheDocument()
})

test('sin precio en línea no muestra un total', async () => {
  window.location.hash = '#/solicitudes/o9'
  const pending = { ...draft, quote: { ...draft.quote, is_complete: false, total_clp: null }, price_pending: 'missing_prices' }
  mockApi({
    'POST /auth/refresh': () => ({ body: customerSession }),
    'GET /portal/requests/o9': () => ({ body: pending }),
  })
  render(<App />)
  expect(await screen.findByText(/aún no tiene precio en línea/)).toBeInTheDocument()
  expect(screen.queryByTestId('request-total')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Descargar PDF' })).not.toBeInTheDocument()
})

test('la dueña ve la solicitud y la acepta con un mensaje', async () => {
  window.location.hash = '#/pedidos'
  const request = {
    id: 'o9',
    customer_name: 'Ana Cliente',
    event_date: '2026-11-21',
    guests: 40,
    status: 'requested',
    notes: 'sin cebolla',
    lines: [{ id: 'l1', recipe_name: 'Empanadas de pino', requested_name: 'empanadas', qty: '5.000', unit: 'dozen' }],
    last_quote_id: 'q9',
    from_customer: true,
    submitted_at: '2026-11-10T13:00:00Z',
    owner_message: null,
  }
  mockApi({
    'POST /auth/refresh': () => ({ body: session }),
    'GET /orders': () => ({ body: [request] }),
    'POST /orders/o9/accept': () => ({ body: { ...request, status: 'confirmed', owner_message: '¡Nos vemos!' } }),
  })
  const user = userEvent.setup()
  render(<App />)
  const card = await screen.findByTestId('request')
  expect(within(card).getByText('Comentario: sin cebolla')).toBeInTheDocument()
  await user.type(within(card).getByLabelText(/Mensaje para el cliente/), '¡Nos vemos!')
  await user.click(within(card).getByRole('button', { name: 'Aceptar' }))
  expect(await screen.findByText(/Solicitud aceptada/)).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByTestId('request')).not.toBeInTheDocument())
  expect(calls.find((c) => c.path === '/orders/o9/accept')?.body).toEqual({ message: '¡Nos vemos!' })
})

test('el cliente elige a qué pyme cotizar y ve los productos de esa pyme', async () => {
  window.location.hash = '#/cotizar'
  mockApi({
    'POST /auth/refresh': () => ({ body: customerSession }),
    'GET /portal/pymes': () => ({ body: pymes }),
    'GET /portal/products': () => ({ body: [{ id: 'r-x', name: 'Producto', yield_unit: 'unit' }] }),
  })
  const user = userEvent.setup()
  render(<App />)
  const select = await screen.findByLabelText(/A qué pyme le quieres cotizar/)
  await waitFor(() => expect(select).toHaveValue('p1')) // por defecto, la de la sesión
  await user.selectOptions(select, 'p2')
  await waitFor(() =>
    expect(calls.some((c) => c.method === 'GET' && c.path === '/portal/products' && c.url?.includes('pyme_id=p2'))).toBe(
      true,
    ),
  )
  await user.click(screen.getByRole('button', { name: 'Ingresar a mano' }))
  expect(screen.getByText('Cotizando con Banquetería Lago')).toBeInTheDocument()
})

test('registro sin enlace: elige la pyme del directorio', async () => {
  window.location.hash = '#/cliente'
  mockApi({
    'POST /auth/refresh': anonymous,
    'GET /portal/directory': () => ({ body: pymes.map((p) => ({ ...p, joined: false })) }),
    'POST /portal/register': () => ({ status: 201, body: customerSession }),
    'GET /portal/requests': () => ({ body: [] }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.selectOptions(await screen.findByLabelText(/Elige la pyme/), 'p2')
  await user.type(screen.getByLabelText('Tu nombre'), 'Ana Cliente')
  await user.type(screen.getByLabelText('Correo'), 'ana@cliente.local')
  await user.type(screen.getByLabelText(/^Contraseña/), 'clave-segura-123')
  await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))
  expect(await screen.findByRole('heading', { name: 'Mis cotizaciones' })).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/portal/register')?.body).toMatchObject({ pyme_id: 'p2' })
})
