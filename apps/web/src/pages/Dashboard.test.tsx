import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken, type Dashboard } from '../api'
import { niceStep } from '../components/charts'
import { formatCLPCompact, formatDay, formatMonth } from '../format'
import { calls, mockApi, session } from '../test/mockApi'

beforeEach(() => {
  window.location.hash = ''
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

const loggedIn = { 'POST /auth/refresh': () => ({ body: session }) }
const collaborator = {
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role: 'collaborator' } } }),
}

const month = (m: string, net: number, cost: number, orders: number) => ({
  month: m,
  orders,
  net_clp: net,
  ingredients_cost_clp: cost,
  margin_clp: net - cost,
  total_clp: Math.round(net * 1.19),
})

const days = Array.from({ length: 14 }, (_, i) => ({
  day: `2026-11-${String(16 + i).padStart(2, '0')}`,
  confirmed: i === 0 ? 2 : 0,
  pending: i === 3 ? 1 : 0,
  guests: i === 0 ? 120 : i === 3 ? 30 : 0,
}))

const data: Dashboard = {
  period: { months: 3, date_from: '2026-09-01', date_to: '2026-11-30', today: '2026-11-16', timezone: 'America/Santiago' },
  kpis: {
    sales_total_clp: 2618000,
    sales_net_clp: 2200000,
    ingredients_cost_clp: 1500000,
    margin_clp: 700000,
    margin_pct: 31.8,
    sold_orders: 9,
    avg_ticket_clp: 290889,
    orders_without_quote: 1,
    pending_requests: 2,
    upcoming_7d: 3,
    low_stock: 1,
  },
  sales_by_month: [month('2026-09', 1000000, 700000, 4), month('2026-10', 0, 0, 0), month('2026-11', 1200000, 800000, 5)],
  orders_by_status: [
    { status: 'requested', orders: 2 },
    { status: 'draft', orders: 1 },
    { status: 'confirmed', orders: 4 },
    { status: 'delivered', orders: 5 },
    { status: 'cancelled', orders: 0 },
  ],
  top_products: {
    items: [
      { recipe_id: 'r1', name: 'Empanadas de pino', units: '480', orders: 6 },
      { recipe_id: 'r2', name: 'Sopaipillas', units: '120', orders: 2 },
    ],
    excluded_lines: 1,
  },
  upcoming_by_day: days,
  spend_by_supplier: [
    { supplier_id: 's1', name: 'Distribuidora Sur', amount_clp: 900000 },
    { supplier_id: null, name: 'Otros', amount_clp: 100000 },
  ],
  low_stock: {
    items: [
      { ingredient_id: 'i1', name: 'Harina', base_unit: 'g', stock_qty: '2500', min_stock_qty: '10000', pct_of_min: 25 },
    ],
    total: 1,
  },
  generated_at: '2026-11-16T12:00:00Z',
}

test('formatos y escala de los gráficos', () => {
  expect(formatCLPCompact(1250000)).toBe('$1,3 M')
  expect(formatCLPCompact(450000)).toBe('$450 mil')
  expect(formatCLPCompact(0)).toBe('$0')
  expect(formatMonth('2026-09')).toBe('sept')
  expect(formatMonth('2026-09', true)).toBe('septiembre 2026')
  expect(formatDay('2026-11-16')).toEqual({ short: 'lu 16', long: 'lunes 16 de noviembre' })
  expect(niceStep(1_200_000)).toBe(500_000)
  expect(niceStep(7)).toBe(2)
  expect(niceStep(0)).toBe(1)
})

test('la dueña entra a "Mi negocio" desde el inicio y ve cifras, gráficos y tablas', async () => {
  mockApi({ ...loggedIn, 'GET /dashboard': () => ({ body: data }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: /Mi negocio/ }))
  expect(await screen.findByTestId('dashboard-period')).toHaveTextContent('De septiembre 2026 a noviembre 2026.')
  expect(calls.find((c) => c.path === '/dashboard')?.url).toContain('months=6')

  const tiles = screen.getByRole('list', { name: 'Mi negocio' })
  expect(within(tiles).getByText('$2.618.000')).toBeInTheDocument()
  expect(within(tiles).getByText('$700.000')).toBeInTheDocument()
  expect(within(tiles).getByText('31,8 % de la venta neta')).toBeInTheDocument()
  expect(screen.getByText(/1 pedido confirmado no tiene cotización aceptada/)).toBeInTheDocument()
  expect(screen.getByText('Tienes 2 solicitudes de clientes por responder.')).toBeInTheDocument()

  // Venta por mes: leyenda de 2 series, cada columna con nombre accesible y la tabla con todas las cifras.
  const sales = screen.getByRole('region', { name: 'Venta por mes' })
  expect(within(sales).getByRole('list', { name: 'Leyenda' })).toHaveTextContent('InsumosMargen')
  expect(within(sales).getByRole('img', { name: 'septiembre 2026: Insumos $700.000, Margen $300.000' })).toBeInTheDocument()
  await user.click(within(sales).getByText('Ver como tabla'))
  const table = within(sales).getByRole('table')
  expect(within(table).getByRole('row', { name: /noviembre 2026/ })).toHaveTextContent('$1.200.000')

  // Tooltip con el teclado.
  within(sales).getByRole('img', { name: /noviembre 2026/ }).focus()
  expect(await within(sales).findByText('5 pedidos')).toBeInTheDocument()

  const products = screen.getByRole('region', { name: 'Productos más pedidos' })
  expect(within(products).getByText('480 unid.')).toBeInTheDocument()
  expect(within(products).getByText(/1 línea pedida por peso/)).toBeInTheDocument()

  const low = screen.getByRole('region', { name: 'Insumos por acabarse' })
  expect(within(low).getByRole('meter', { name: 'Harina: Quedan 2,5 kg de 10 kg mínimo' })).toHaveAttribute('aria-valuenow', '25')
  expect(within(low).getByRole('link')).toHaveAttribute('href', '#/inventario/i1')

  const status = screen.getByRole('region', { name: 'Pedidos por estado' })
  expect(within(status).getByText('Por responder')).toBeInTheDocument()

  // Cambiar el periodo pide de nuevo con los meses elegidos.
  await user.click(screen.getByRole('button', { name: '12 meses' }))
  expect(screen.getByRole('button', { name: '12 meses' })).toHaveAttribute('aria-pressed', 'true')
  expect(calls.some((c) => c.url?.includes('months=12'))).toBe(true)
})

test('sin ventas muestra cómo aparecen, en vez de un gráfico vacío', async () => {
  const empty: Dashboard = {
    ...data,
    kpis: { ...data.kpis, sold_orders: 0, sales_total_clp: 0, margin_clp: 0, margin_pct: null, avg_ticket_clp: null, orders_without_quote: 0, pending_requests: 0 },
    sales_by_month: data.sales_by_month.map((m) => month(m.month, 0, 0, 0)),
    upcoming_by_day: days.map((x) => ({ ...x, confirmed: 0, pending: 0, guests: 0 })),
    top_products: { items: [], excluded_lines: 0 },
    spend_by_supplier: [],
    low_stock: { items: [], total: 0 },
  }
  window.location.hash = '#/tablero'
  mockApi({ ...loggedIn, 'GET /dashboard': () => ({ body: empty }) })
  render(<App />)
  expect(await screen.findByText(/Todavía no hay ventas en este periodo/)).toBeInTheDocument()
  expect(screen.getByText('Sin eventos en los próximos 14 días.')).toBeInTheDocument()
  expect(screen.getByText('Todos tus insumos están sobre su mínimo.')).toBeInTheDocument()
  expect(screen.queryByText(/solicitudes de clientes por responder/)).not.toBeInTheDocument()
})

test('la colaboradora no ve el tablero ni su acceso', async () => {
  window.location.hash = '#/tablero'
  mockApi({ ...collaborator })
  render(<App />)
  expect(await screen.findByText('Solo la dueña puede ver el tablero del negocio.')).toBeInTheDocument()
  expect(calls.some((c) => c.path === '/dashboard')).toBe(false)
  window.location.hash = '#/'
  expect(await screen.findByRole('button', { name: /Cotizar/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Mi negocio/ })).not.toBeInTheDocument()
})
