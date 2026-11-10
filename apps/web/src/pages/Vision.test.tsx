import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory, setItem, setScope } from '../offline/db'
import { listPhotos } from '../offline/photos'
import { pendingOps } from '../offline/queue'
import { calls, mockApi, session, type Routes } from '../test/mockApi'

const recipes = [
  { id: 'r-pino', name: 'Empanadas de pino', yield_unit: 'unit', is_active: true, is_final_product: true },
  { id: 'r-can', name: 'Canapés de salmón', yield_unit: 'unit', is_active: true, is_final_product: true },
  { id: 'r-masa', name: 'Masa base', yield_unit: 'g', is_active: true, is_final_product: false },
]

const count = {
  model_version: 'snacks-v1-nano-1',
  elapsed_ms: 420,
  counts: [
    { vision_class: 'empanada_pino', count: 3, recipe_id: 'r-pino', recipe_name: 'Empanadas de pino' },
    { vision_class: 'canape', count: 2, recipe_id: null, recipe_name: null },
  ],
  detections: [
    { vision_class: 'empanada_pino', score: 0.9, box: [0.1, 0.1, 0.3, 0.3] },
    { vision_class: 'empanada_pino', score: 0.8, box: [0.4, 0.1, 0.6, 0.3] },
    { vision_class: 'empanada_pino', score: 0.7, box: [0.7, 0.1, 0.9, 0.3] },
    { vision_class: 'canape', score: 0.9, box: [0.1, 0.5, 0.3, 0.7] },
    { vision_class: 'canape', score: 0.6, box: [0.4, 0.5, 0.6, 0.7] },
  ],
}

const base: Routes = {
  'POST /auth/refresh': () => ({ body: session }),
  'GET /recipes': () => ({ body: recipes }),
  'POST /vision/productions': () => ({ status: 201, body: { id: 'pr1', replayed: false } }),
  'POST /metrics/survey': () => ({ status: 201, body: {} }),
}

const photo = () => new File([new Uint8Array([137, 80, 78, 71])], 'bandeja.png', { type: 'image/png' })

beforeEach(() => {
  window.location.hash = '#/foto'
  setAccessToken(null)
  resetMemory()
})
afterEach(() => {
  vi.restoreAllMocks()
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
})

test('cuenta la foto, se corrige con +/− y confirma con Idempotency-Key', async () => {
  const spy = mockApi({ ...base, 'POST /vision/count': () => ({ body: count }) })
  const user = userEvent.setup()
  render(<App />)
  await user.upload(await screen.findByLabelText('Elegir foto'), photo())
  expect(await screen.findByText('Esto conté')).toBeInTheDocument()
  expect(screen.getByText('Detecté 3')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Uno menos de Empanadas de pino' }))
  // la clase sin receta exige elegir producto antes de confirmar
  await user.click(screen.getByRole('button', { name: 'Confirmar producción' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Elige el producto')
  expect(calls.some((c) => c.path === '/vision/productions')).toBe(false)

  await user.selectOptions(screen.getByLabelText('Producto'), 'r-can')
  expect(screen.queryByRole('option', { name: 'Masa base' })).not.toBeInTheDocument() // solo productos finales
  await user.click(screen.getByRole('button', { name: 'Uno más de Canapés de salmón' }))
  await user.click(screen.getByRole('button', { name: 'Confirmar producción' }))

  expect(await screen.findByText('Producción registrada.')).toBeInTheDocument()
  await waitFor(() => expect(calls.filter((c) => c.path === '/vision/productions')).toHaveLength(2))
  const sent = calls.filter((c) => c.path === '/vision/productions').map((c) => c.body as Record<string, unknown>)
  expect(sent[0]).toMatchObject({ recipe_id: 'r-pino', confirmed_qty: 2, detected_qty: 3, model_version: 'snacks-v1-nano-1' })
  expect((sent[0].detections as unknown[]).length).toBe(3)
  expect(sent[1]).toMatchObject({ recipe_id: 'r-can', confirmed_qty: 3, detected_qty: 2 })
  const keys = spy.mock.calls
    .filter(([input]) => String(input).endsWith('/vision/productions'))
    .map(([, init]) => new Headers(init?.headers).get('Idempotency-Key'))
  expect(keys).toHaveLength(2)
  expect(keys.every((k) => k && /^[0-9a-f-]{36}$/.test(k))).toBe(true)
  expect(new Set(keys).size).toBe(2)
  expect(screen.getByRole('button', { name: '5 estrellas' })).toBeInTheDocument() // encuesta de 1 a 5
  expect(screen.getByRole('button', { name: 'Contar otra bandeja' })).toBeInTheDocument()
})

test('sin modelo (503) ofrece registrar a mano', async () => {
  mockApi({
    ...base,
    'POST /vision/count': () => ({
      status: 503,
      body: { code: 'vision_model_unavailable', title: 'El conteo por foto no está disponible' },
    }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.upload(await screen.findByLabelText('Sacar foto'), photo())
  expect(await screen.findByText(/no está disponible ahora/)).toBeInTheDocument()
  expect(screen.getByText('Registrar a mano')).toBeInTheDocument()

  await user.selectOptions(screen.getByLabelText('Producto'), 'r-pino')
  await user.type(screen.getByLabelText('Cantidad'), '24')
  await user.click(screen.getByRole('button', { name: 'Confirmar producción' }))
  expect(await screen.findByText('Producción registrada.')).toBeInTheDocument()
  await waitFor(() =>
    expect(calls.find((c) => c.path === '/vision/productions')?.body).toEqual({ recipe_id: 'r-pino', confirmed_qty: 24 }),
  )
})

test('sin conexión guarda la foto para después y el registro manual queda en cola', async () => {
  Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
  setScope('p1')
  await setItem('cache:recipes', { data: recipes, savedAt: '2026-11-09T12:00:00Z' })
  mockApi(base)
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByText(/puedes guardar la foto para contarla al volver/)).toBeInTheDocument()

  await user.upload(screen.getByLabelText('Elegir foto'), photo())
  await user.click(await screen.findByRole('button', { name: 'Guardar foto para después' }))
  expect(await screen.findByText(/Foto guardada/)).toBeInTheDocument()
  expect(screen.getByText('Tienes 1 foto por contar')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Contar ahora' })).toBeDisabled()
  expect(await listPhotos()).toHaveLength(1)
  expect(calls.some((c) => c.path === '/vision/count')).toBe(false)

  await user.click(screen.getByRole('button', { name: 'Contar a mano' }))
  await user.selectOptions(screen.getByLabelText('Producto'), 'r-can')
  await user.type(screen.getByLabelText('Cantidad'), '12')
  await user.click(screen.getByRole('button', { name: 'Confirmar producción' }))
  expect(await screen.findByText(/Se enviará al volver la señal/)).toBeInTheDocument()
  const queued = await pendingOps()
  expect(queued).toHaveLength(1)
  expect(queued[0].body).toEqual({ recipe_id: 'r-can', confirmed_qty: 12 })
  expect(calls.some((c) => c.path === '/vision/productions')).toBe(false)
})

test('con señal cuenta la foto guardada y la quita de la lista', async () => {
  setScope('p1')
  await setItem('photos:pending', [{ id: 'f1', blob: new Blob([new Uint8Array([1, 2, 3])]), createdAt: '2026-11-09T12:00:00Z' }])
  mockApi({ ...base, 'POST /vision/count': () => ({ body: { ...count, counts: [count.counts[0]], detections: count.detections.slice(0, 3) } }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Contar ahora' }))
  expect(await screen.findByText('Detecté 3')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Confirmar producción' }))
  expect(await screen.findByText('Producción registrada.')).toBeInTheDocument()
  expect(await listPhotos()).toHaveLength(0)
})
