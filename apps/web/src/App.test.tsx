import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import { setAccessToken } from './api'
import { calls, incompleteQuote, mockApi, recipes, session } from './test/mockApi'

beforeEach(() => {
  window.location.hash = ''
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

const loggedIn = { 'POST /auth/refresh': () => ({ body: session }) }

test('sin sesión muestra el login y al entrar muestra el inicio', async () => {
  mockApi({
    'POST /auth/refresh': () => ({ status: 401, body: { code: 'session_expired', title: 'Tu sesión venció' } }),
    'POST /auth/login': (b) =>
      (b as { password: string }).password === 'buena-clave'
        ? { body: session }
        : { status: 401, body: { code: 'invalid_credentials', title: 'Correo o contraseña incorrectos' } },
  })
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Correo'), 'duena@demo.local')
  await user.type(screen.getByLabelText('Contraseña'), 'mala')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Correo o contraseña incorrectos')
  await user.clear(screen.getByLabelText('Contraseña'))
  await user.type(screen.getByLabelText('Contraseña'), 'buena-clave')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(await screen.findByText('Hola, Dueña')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Cotizar un pedido/ })).toBeEnabled()
  expect(screen.getByRole('button', { name: /Contar con foto/ })).toBeDisabled()
})

test('lee un pedido, ofrece sugerencias, se edita y genera la cotización', async () => {
  mockApi({
    ...loggedIn,
    'GET /recipes': () => ({ body: recipes }),
    'POST /orders/extract': () => ({
      body: {
        guests: 40,
        event_date: '2026-11-14',
        event_date_text: 'sábado',
        needs_review: true,
        extraction: { model: 'qwen3:4b' },
        lines: [
          { requested_name: 'empanaditas de pino', qty: '80', unit: 'unit', recipe_id: 'r-pino',
            recipe_name: 'Empanadas de pino', suggestions: [], warning: null },
          { requested_name: 'empanadas', qty: '2', unit: 'dozen', recipe_id: null, recipe_name: null,
            suggestions: [{ recipe_id: 'r-pino', recipe_name: 'Empanadas de pino', score: 100 },
                          { recipe_id: 'r-queso', recipe_name: 'Empanadas de queso', score: 100 }],
            warning: '¿Cuál de tus recetas es?' },
        ],
      },
    }),
    'POST /orders': () => ({ status: 201, body: { id: 'o1', lines: [] } }),
    'POST /orders/o1/quotes': () => ({ status: 201, body: { ...incompleteQuote, id: 'q9' } }),
  })
  window.location.hash = '#/cotizar'
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText(/Pega aquí/), '80 empanaditas de pino y 2 docenas de empanadas')
  await user.click(screen.getByRole('button', { name: 'Leer pedido' }))

  expect(await screen.findByText('¿Cuál de tus recetas es?')).toBeInTheDocument()
  expect(screen.getByLabelText('Invitados')).toHaveValue(40)
  expect(screen.getByLabelText('Fecha del evento')).toHaveValue('2026-11-14')
  // sin nombre del cliente no deja seguir
  await user.click(screen.getByRole('button', { name: 'Calcular cotización' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Escribe el nombre del cliente')
  await user.type(screen.getByLabelText('Nombre del cliente'), 'Cliente Prueba')
  // sin receta en la segunda línea tampoco
  await user.click(screen.getByRole('button', { name: 'Calcular cotización' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Falta elegir la receta')
  await user.click(screen.getByRole('button', { name: 'Empanadas de queso' }))
  const qty = screen.getAllByLabelText('Cantidad')[1]
  await user.clear(qty)
  await user.type(qty, '2,5')
  await user.click(screen.getByRole('button', { name: 'Calcular cotización' }))

  await waitFor(() => expect(window.location.hash).toBe('#/cotizaciones/q9'))
  const order = calls.find((c) => c.method === 'POST' && c.path === '/orders')?.body as Record<string, unknown>
  expect(order.customer_name).toBe('Cliente Prueba')
  expect(order.source).toBe('text')
  expect(order.lines).toEqual([
    { recipe_id: 'r-pino', requested_name: 'empanaditas de pino', qty: '80', unit: 'unit' },
    { recipe_id: 'r-queso', requested_name: 'empanadas', qty: '2.5', unit: 'dozen' },
  ])
  const quoteCall = calls.find((c) => c.path === '/orders/o1/quotes')?.body as Record<string, unknown>
  expect(quoteCall.started_at).toMatch(/^\d{4}-\d{2}-\d{2}T/)
})

test('si la IA no puede leer el pedido, ofrece el formulario a mano', async () => {
  mockApi({
    ...loggedIn,
    'GET /recipes': () => ({ body: recipes }),
    'POST /orders/extract': () => ({
      status: 422,
      body: { code: 'extraction_failed', title: 'No pude interpretar el pedido', detail: 'Ingrésalo con el formulario; así no se pierde nada.' },
    }),
  })
  window.location.hash = '#/cotizar'
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText(/Pega aquí/), 'texto confuso')
  await user.click(screen.getByRole('button', { name: 'Leer pedido' }))
  expect(await screen.findByText(/No pude interpretar el pedido/)).toBeInTheDocument()
  expect(screen.getByText('Paso 2 de 2: revisa y confirma')).toBeInTheDocument()
  expect(screen.getAllByTestId('order-line')).toHaveLength(1)
  expect(screen.getByLabelText('Receta 1')).toHaveValue('')
})

test('la colaboradora ve un mensaje claro si intenta cotizar', async () => {
  mockApi({
    ...loggedIn,
    'GET /recipes': () => ({ body: recipes }),
    'POST /orders': () => ({ status: 201, body: { id: 'o2', lines: [] } }),
    'POST /orders/o2/quotes': () => ({ status: 403, body: { code: 'owner_only', title: 'Solo la dueña puede hacer esto' } }),
  })
  window.location.hash = '#/cotizar'
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Ingresar a mano' }))
  await user.type(screen.getByLabelText('Nombre del cliente'), 'Cliente X')
  await user.selectOptions(screen.getByLabelText('Receta 1'), 'r-sopa')
  await user.type(screen.getByLabelText('Cantidad'), '24')
  await user.click(screen.getByRole('button', { name: 'Calcular cotización' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Solo la dueña puede generar cotizaciones')
})

test('una cotización incompleta muestra qué precio falta y no ofrece el PDF', async () => {
  mockApi({ ...loggedIn, 'GET /quotes/q1': () => ({ body: incompleteQuote }) })
  window.location.hash = '#/cotizaciones/q1'
  render(<App />)
  expect(await screen.findByText('Esta cotización está incompleta')).toBeInTheDocument()
  expect(screen.getByText(/Falta el precio de: Eneldo/)).toBeInTheDocument()
  expect(screen.getByTestId('quote-total')).toHaveTextContent('$99.484')
  expect(screen.getAllByText('$83.600')).toHaveLength(2) // subtotal y neto
  expect(screen.getByRole('button', { name: 'Volver a calcular' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Ver PDF' })).toBeNull()
})

test('ante un 401 renueva la sesión una vez y reintenta', async () => {
  let refreshes = 0
  let first = true
  mockApi({
    'POST /auth/refresh': () => {
      refreshes += 1
      return { body: session }
    },
    'GET /quotes/q1': () => {
      if (first) {
        first = false
        return { status: 401, body: { code: 'unauthorized', title: 'Necesitas iniciar sesión' } }
      }
      return { body: { ...incompleteQuote, is_complete: true, missing_prices: [] } }
    },
  })
  window.location.hash = '#/cotizaciones/q1'
  await act(async () => {
    render(<App />)
  })
  expect(await screen.findByRole('button', { name: 'Ver PDF' })).toBeInTheDocument()
  expect(refreshes).toBe(2) // al abrir la app y tras el 401
})
