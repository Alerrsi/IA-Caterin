import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session } from '../test/mockApi'

const base = (id: string, name: string, unit: 'g' | 'ml' | 'unit', stock: string, min: string | null) => ({
  id,
  name,
  base_unit: unit,
  stock_qty: stock,
  min_stock_qty: min,
  waste_pct: null,
  category: null,
  is_active: true,
  is_low: min !== null && Number(stock) < Number(min),
  updated_at: '2026-11-09T12:00:00Z',
})

function routes() {
  const stock: Record<string, string> = { sal: '3000.000', azucar: '500.000', huevo: '30.000' }
  const items = () => [
    base('sal', 'Sal', 'g', stock.sal, '1000.000'),
    base('azucar', 'Azúcar flor', 'g', stock.azucar, '1000.000'),
    base('huevo', 'Huevos', 'unit', stock.huevo, null),
  ]
  return {
    stock,
    routes: {
      'POST /auth/refresh': () => ({ body: session }),
      'GET /ingredients': () => ({ body: { items: items(), next_cursor: null } }),
      'POST /stock/movements': (body: unknown) => {
        const b = body as { ingredient_id: string; delta_qty: string; unit: string }
        const factor = b.unit === 'kg' ? 1000 : 1
        stock[b.ingredient_id] = (Number(stock[b.ingredient_id]) + Number(b.delta_qty) * factor).toFixed(3)
        return { status: 201, body: {} }
      },
    },
  }
}

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })
  window.dispatchEvent(new Event(value ? 'online' : 'offline'))
}

beforeEach(() => {
  resetMemory()
  window.location.hash = '#/inventario'
  setAccessToken(null)
})
afterEach(() => {
  vi.restoreAllMocks()
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
})

test('lista con stock legible, bajo el mínimo y búsqueda sin tildes', async () => {
  mockApi(routes().routes)
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText('Sal')).toBeInTheDocument()
  expect(screen.getByText('3 kg')).toBeInTheDocument()
  expect(screen.getByText('30 unid.')).toBeInTheDocument()
  expect(screen.getByText(/Bajo el mínimo · mínimo 1 kg/)).toBeInTheDocument() // azúcar: 500 g < 1 kg
  await user.type(screen.getByLabelText('Buscar insumo'), 'azucar')
  expect(screen.getByText('Azúcar flor')).toBeInTheDocument()
  expect(screen.queryByText('Sal')).not.toBeInTheDocument()
  await user.clear(screen.getByLabelText('Buscar insumo'))
  await user.click(screen.getByLabelText('Solo lo que falta'))
  expect(screen.getAllByRole('listitem')).toHaveLength(1)
})

test('sumar encola el movimiento, lo envía con Idempotency-Key y actualiza el stock', async () => {
  const spy = mockApi(routes().routes)
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Sumar a Sal' }))
  await user.type(screen.getByLabelText('Cantidad'), '1,5')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect(await screen.findByText('4,5 kg')).toBeInTheDocument()
  await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/stock/movements')).toBe(true))
  const sent = calls.find((c) => c.path === '/stock/movements')!
  expect(sent.body).toMatchObject({ ingredient_id: 'sal', reason: 'purchase', delta_qty: '1.5', unit: 'kg' })
  expect(typeof (sent.body as { occurred_at: string }).occurred_at).toBe('string')
  const init = spy.mock.calls.find(([url]) => String(url).endsWith('/stock/movements'))![1]!
  expect(new Headers(init.headers).get('Idempotency-Key')).toMatch(/^[0-9a-f-]{36}$/)
})

test('restar valida la cantidad y avisa si el stock queda negativo', async () => {
  mockApi(routes().routes)
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Restar a Huevos' }))
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Escribe una cantidad mayor que cero')
  await user.type(screen.getByLabelText('Cantidad'), '3')
  await user.selectOptions(screen.getByLabelText('Unidad'), 'docena')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect(await screen.findByText('-6 unid.')).toBeInTheDocument()
  expect(screen.getByText(/el stock quedó negativo/)).toBeInTheDocument()
  await waitFor(() =>
    expect(calls.find((c) => c.path === '/stock/movements')?.body).toMatchObject({
      reason: 'consumption',
      delta_qty: '-3',
      unit: 'docena',
    }),
  )
})

test('sin señal el cambio queda pendiente y se envía al volver', async () => {
  mockApi(routes().routes)
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Sal')
  setOnline(false)
  await user.click(screen.getByRole('button', { name: 'Restar a Sal' }))
  await user.type(screen.getByLabelText('Cantidad'), '1')
  await user.selectOptions(screen.getByLabelText('Motivo'), 'adjustment')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect(await screen.findByText('2 kg')).toBeInTheDocument()
  expect(await screen.findByText('1 cambio por enviar')).toBeInTheDocument()
  expect(screen.getByText(/Se enviará al volver la señal/)).toBeInTheDocument()
  const row = screen.getByText('Sal').closest('li')!
  expect(within(row).getByText('Por enviar')).toBeInTheDocument()
  expect(calls.some((c) => c.path === '/stock/movements')).toBe(false)

  setOnline(true)
  await waitFor(() => expect(calls.filter((c) => c.path === '/stock/movements')).toHaveLength(1))
  await waitFor(() => expect(screen.queryByText('1 cambio por enviar')).not.toBeInTheDocument())
  await waitFor(() => expect(within(screen.getByText('Sal').closest('li')!).queryByText('Por enviar')).toBeNull())
  expect(screen.getByText('2 kg')).toBeInTheDocument() // dato del servidor tras sincronizar
})

test('sin señal y con datos guardados muestra la fecha; sin datos guardados lo explica', async () => {
  mockApi(routes().routes)
  const first = render(<App />)
  await screen.findByText('Sal')
  first.unmount()
  setOnline(false)
  render(<App />)
  expect(await screen.findByText(/Sin conexión: datos guardados el/)).toBeInTheDocument()
  expect(screen.getByText('Sal')).toBeInTheDocument()
})

test('sin señal y sin nada guardado lo explica', async () => {
  mockApi(routes().routes)
  setOnline(false)
  render(<App />)
  expect(await screen.findByText(/todavía no hay datos guardados en este teléfono/)).toBeInTheDocument()
})

test('el detalle muestra el historial y permite ajustar', async () => {
  const r = routes()
  mockApi({
    ...r.routes,
    'GET /ingredients/sal/movements': () => ({
      body: {
        items: [
          {
            id: 'm1',
            ingredient_id: 'sal',
            delta_qty: '-500.000',
            reason: 'waste',
            note: null,
            occurred_at: '2026-11-08T15:00:00Z',
          },
        ],
        next_cursor: null,
      },
    }),
  })
  window.location.hash = '#/inventario/sal'
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Sal' })).toBeInTheDocument()
  expect(await screen.findByText('Merma (se perdió)')).toBeInTheDocument()
  expect(screen.getByText('-500 g')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Sumar a Sal' }))
  await user.type(screen.getByLabelText('Cantidad'), '2')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect(await screen.findByText('5 kg')).toBeInTheDocument()
})
