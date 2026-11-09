import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { calls, incompleteQuote, mockApi, session } from '../test/mockApi'

beforeEach(() => {
  window.location.hash = ''
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

const loggedIn = { 'POST /auth/refresh': () => ({ body: session }) }
const collaborator = {
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role: 'collaborator' } } }),
}

const stat = (n: number, value: number | null, unit = 's') => ({ n, value, unit, low_n: n < 5 })

const summary = {
  period: { date_from: '2026-10-11', date_to: '2026-11-09', timezone: 'America/Santiago' },
  low_n_threshold: 5,
  satisfaction: { n: 6, mean_stars: 3.83, distribution: { '1': 0, '2': 1, '3': 1, '4': 2, '5': 2 }, low_n: false },
  quote_time: {
    caterin_median: stat(6, 160.1),
    manual_median: stat(3, 1500),
    manual_range: { first_measured_on: '2026-11-02', last_measured_on: '2026-11-02' },
  },
  data_lookup: {
    assistant_median: stat(0, null),
    manual_median: stat(0, null),
    manual_range: { first_measured_on: null, last_measured_on: null },
  },
  assistant: {
    total: 12,
    levels: [
      { level: 0, n: 7, p50_ms: 180, p95_ms: 970, low_n: false },
      { level: 1, n: 4, p50_ms: 12475, p95_ms: 15770, low_n: true },
      { level: 2, n: 1, p50_ms: 12500, p95_ms: 12500, low_n: true },
    ],
    without_llm: { n: 7, total: 12, pct: 58.3, low_n: false },
    degraded: { n: 2, total: 12, pct: 16.7, low_n: false },
  },
  warnings: ['Cotización manual de referencia: solo 3 mediciones (menos de 5).'],
}

test('la dueña ve sus métricas con n, periodo y advertencias', async () => {
  mockApi({ ...loggedIn, 'GET /metrics/summary': () => ({ body: summary }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: /Mis métricas/ }))
  expect(await screen.findByTestId('metrics-period')).toHaveTextContent('Del 11-10-2026 al 09-11-2026')
  expect(screen.getByText('3,83 de 5 estrellas')).toBeInTheDocument()

  const quote = screen.getByRole('region', { name: 'Tiempo para cotizar (mediana)' })
  expect(within(quote).getByText('2 min 40 s')).toBeInTheDocument()
  expect(within(quote).getByText('25 min')).toBeInTheDocument()
  expect(within(quote).getByText('n = 6')).toBeInTheDocument()
  expect(within(quote).getByText('n = 3')).toBeInTheDocument()
  expect(within(quote).getAllByText(/Pocas mediciones \(menos de 5\)/)).toHaveLength(1)

  const assistant = screen.getByRole('region', { name: 'Asistente' })
  expect(within(assistant).getByText('58,3 %')).toBeInTheDocument()
  expect(within(assistant).getByText('16,7 %')).toBeInTheDocument()
  expect(within(assistant).getAllByText('12,5 s')).toHaveLength(3) // p50 del nivel 1 y p50/p95 del nivel 2
  expect(screen.getByText(/solo 3 mediciones/)).toBeInTheDocument()
  // el periodo por defecto son los últimos 30 días
  expect(calls.find((c) => c.path === '/metrics/summary')).toBeDefined()

  const lookup = screen.getByRole('region', { name: 'Buscar un dato (mediana)' })
  expect(within(lookup).getAllByText('Sin datos')).toHaveLength(2)
})

test('cambiar el periodo vuelve a pedir el resumen', async () => {
  const urls: string[] = []
  const spy = mockApi({ ...loggedIn, 'GET /metrics/summary': () => ({ body: summary }) })
  window.location.hash = '#/metricas'
  const user = userEvent.setup()
  render(<App />)
  await screen.findByTestId('metrics-period')
  await user.selectOptions(screen.getByLabelText('Periodo'), 'all')
  await waitFor(() => {
    for (const [input] of spy.mock.calls) urls.push(String(input))
    expect(urls.some((u) => u.endsWith('/metrics/summary'))).toBe(true)
  })
  expect(urls.some((u) => /\/metrics\/summary\?from=\d{4}-\d{2}-\d{2}$/.test(u))).toBe(true)
})

test('registra una medición manual con minutos y segundos', async () => {
  mockApi({
    ...loggedIn,
    'GET /metrics/summary': () => ({ body: summary }),
    'POST /metrics/manual-baseline': () => ({ status: 201, body: {} }),
  })
  window.location.hash = '#/metricas'
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByText('Registrar una medición a mano'))
  await user.type(screen.getByLabelText('Segundos'), '75')
  await user.click(screen.getByRole('button', { name: 'Guardar medición' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Revisa el tiempo')
  await user.clear(screen.getByLabelText('Segundos'))
  await user.type(screen.getByLabelText('Minutos'), '24')
  await user.type(screen.getByLabelText('Segundos'), '30')
  await user.type(screen.getByLabelText(/Caso medido/), 'pedido de referencia P1')
  await user.type(screen.getByLabelText('Herramienta usada'), 'Excel')
  await user.click(screen.getByRole('button', { name: 'Guardar medición' }))
  expect(await screen.findByText('Medición guardada.')).toBeInTheDocument()
  const body = calls.find((c) => c.path === '/metrics/manual-baseline')?.body as Record<string, unknown>
  expect(body).toMatchObject({ task: 'quote', seconds: 1470, reference: 'pedido de referencia P1', repetition: 1, tool: 'Excel' })
  expect(screen.getByLabelText('Repetición n.º')).toHaveValue(2)
})

test('descarga el CSV', async () => {
  mockApi({
    ...loggedIn,
    'GET /metrics/summary': () => ({ body: summary }),
    'GET /metrics/summary.csv': () => ({ body: 'seccion;metrica' }),
  })
  const createUrl = vi.fn(() => 'blob:csv')
  Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  window.location.hash = '#/metricas'
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Descargar CSV' }))
  await waitFor(() => expect(click).toHaveBeenCalled())
  expect(createUrl).toHaveBeenCalled()
  expect(calls.some((c) => c.path === '/metrics/summary.csv')).toBe(true)
})

test('la colaboradora no ve el panel de métricas', async () => {
  mockApi({ ...collaborator })
  render(<App />)
  expect(await screen.findByText('Hola, Dueña')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Mis métricas/ })).toBeNull()
  window.location.hash = '#/metricas'
  expect(await screen.findByText('Solo la dueña puede ver las métricas.')).toBeInTheDocument()
  expect(calls.some((c) => c.path.startsWith('/metrics'))).toBe(false)
})

test('la encuesta de estrellas se envía con un toque', async () => {
  mockApi({
    ...loggedIn,
    'GET /quotes/q1': () => ({ body: incompleteQuote }),
    'POST /metrics/survey': () => ({ status: 201, body: {} }),
  })
  window.location.hash = '#/cotizaciones/q1'
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: '4 estrellas' }))
  expect(await screen.findByText(/Gracias/)).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/metrics/survey')?.body).toEqual({ stars: 4, context: 'quote' })
})
