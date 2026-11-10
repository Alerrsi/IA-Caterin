import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { calls, mockApi, session, type Routes } from '../test/mockApi'

const quick = [
  { id: 'low_stock', label: '¿Qué me falta?', question: '¿Qué me falta comprar?' },
  { id: 'orders_week', label: 'Pedidos de esta semana', question: '¿Qué pedidos tengo esta semana?' },
]

const base: Routes = {
  'POST /auth/refresh': () => ({ body: session }),
  'GET /assistant/quick-actions': () => ({ body: quick }),
  'POST /assistant/feedback': () => ({ status: 204 }),
}

function done(answer: string, extra: Record<string, unknown> = {}) {
  return {
    interaction_id: 'i1',
    answer,
    level: 0,
    intent: 'stock_of_item',
    status: 'ok',
    sources: [{ kind: 'inventory', label: 'tu inventario' }],
    options: [],
    fallback_reason: null,
    cache_hit: false,
    latency_ms: 12,
    ...extra,
  }
}

/** Respuesta SSE real (cuerpo en *streaming*), con los eventos en trozos que cortan líneas a la mitad. */
function sse(events: [string, unknown][]): Response {
  const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
  const pieces = [text.slice(0, 17), text.slice(17, 60), text.slice(60)]
  const body = new ReadableStream({
    start(controller) {
      for (const p of pieces) controller.enqueue(new TextEncoder().encode(p))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

/** Igual que mockApi, pero `POST /assistant/ask` responde SSE. */
function mockWithStream(events: [string, unknown][]) {
  const json = mockApi(base)
  const fallback = json.getMockImplementation()!
  json.mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (url.endsWith('/assistant/ask')) {
      calls.push({ method: 'POST', path: '/assistant/ask', body: JSON.parse(String(init?.body)) })
      return sse(events)
    }
    return fallback(input, init)
  })
}

beforeEach(() => {
  window.location.hash = '#/preguntar'
  setAccessToken(null)
})
afterEach(() => {
  vi.restoreAllMocks()
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
})

test('pregunta con streaming: muestra el texto, la fuente y guarda el feedback', async () => {
  const meta = { intent: 'recipe_cost', status: 'ok', drafting: true, sources: [{ kind: 'recipe_cost', label: 'tus recetas' }], options: [], cache_hit: false }
  mockWithStream([
    ['meta', meta],
    ['delta', { text: 'La docena cuesta ' }],
    ['delta', { text: '$9.156.' }],
    ['done', done('La docena cuesta $9.156.', { level: 1, sources: meta.sources })],
  ])
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Tu pregunta'), '¿Cuánto me sale la docena de empanadas?')
  await user.click(screen.getByRole('button', { name: 'Preguntar' }))
  expect(await screen.findByText('La docena cuesta $9.156.')).toBeInTheDocument()
  expect(screen.getByText(/Fuente: tus recetas/)).toBeInTheDocument()
  const ask = calls.find((c) => c.path === '/assistant/ask')
  expect(ask?.body).toEqual({ question: '¿Cuánto me sale la docena de empanadas?' })

  await user.click(screen.getByRole('button', { name: 'Me sirvió' }))
  expect(await screen.findByText(/Gracias, lo usaremos/)).toBeInTheDocument()
  await waitFor(() =>
    expect(calls.find((c) => c.path === '/assistant/feedback')?.body).toEqual({ interaction_id: 'i1', useful: true }),
  )
})

test('si el LLM inventa una cifra, se reemplaza el texto por la plantilla', async () => {
  mockWithStream([
    ['meta', { intent: 'recipe_cost', status: 'ok', drafting: true, sources: [], options: [], cache_hit: false }],
    ['delta', { text: 'Te cuesta ' }],
    ['replace', { text: 'Producir 12 unidades te cuesta $9.156.', fallback_reason: 'figures_mismatch' }],
    ['done', done('Producir 12 unidades te cuesta $9.156.', { fallback_reason: 'figures_mismatch' })],
  ])
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Tu pregunta'), 'cuanto cuesta')
  await user.click(screen.getByRole('button', { name: 'Preguntar' }))
  expect(await screen.findByText('Producir 12 unidades te cuesta $9.156.')).toBeInTheDocument()
  expect(screen.queryByText(/^Te cuesta $/)).not.toBeInTheDocument()
})

test('las acciones rápidas van directo y las opciones se pueden tocar', async () => {
  let n = 0
  mockApi({
    ...base,
    'POST /assistant/ask': () => {
      n += 1
      return n === 1
        ? {
            body: done('¿A cuál insumo te refieres?', {
              status: 'ambiguous',
              sources: [],
              options: [{ label: 'Crema de leche', question: '¿Cuánto me queda de Crema de leche?' }],
            }),
          }
        : { body: done('Te quedan 2 L de Crema de leche.') }
    },
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: '¿Qué me falta?' }))
  expect(calls.find((c) => c.path === '/assistant/ask')?.body).toEqual({
    question: '¿Qué me falta comprar?',
    quick_action: 'low_stock',
  })
  await user.click(await screen.findByRole('button', { name: 'Crema de leche' }))
  expect(await screen.findByText('Te quedan 2 L de Crema de leche.')).toBeInTheDocument()
  expect(calls.filter((c) => c.path === '/assistant/ask').at(-1)?.body).toEqual({
    question: '¿Cuánto me queda de Crema de leche?',
  })
})

test('muestra el error de la API sin romper la pantalla', async () => {
  mockApi({ ...base, 'POST /assistant/ask': () => ({ status: 422, body: { code: 'validation_error', title: 'Revisa la pregunta' } }) })
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Tu pregunta'), 'hola')
  await user.click(screen.getByRole('button', { name: 'Preguntar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Revisa la pregunta')
  expect(screen.getByLabelText('Tu pregunta')).toBeEnabled()
})

test('sin conexión avisa y no deja preguntar', async () => {
  Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
  mockApi(base)
  render(<App />)
  expect(await screen.findByText(/para preguntar necesitas internet/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Preguntar' })).toBeDisabled()
})
