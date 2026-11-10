import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { setAccessToken } from '../api'
import { fetchCached, patchCached } from './cache'
import { resetMemory, setScope } from './db'
import { dismissFailed, enqueue, failedOps, flush, pendingOps } from './queue'

type Reply = { status: number; body?: unknown } | 'network'

/** fetch simulado que responde en orden y guarda método, ruta y la clave de idempotencia de cada intento. */
function fakeFetch(replies: Reply[]) {
  const seen: { path: string; key: string | null; body: unknown }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const path = url.replace(/^.*\/api\/v1/, '')
    if (path === '/auth/refresh') return new Response('{}', { status: 401 })
    const headers = new Headers(init?.headers)
    seen.push({ path, key: headers.get('Idempotency-Key'), body: init?.body ? JSON.parse(String(init.body)) : null })
    const r = replies.shift() ?? { status: 201 }
    if (r === 'network') throw new TypeError('Failed to fetch')
    const type = r.status >= 400 ? 'application/problem+json' : 'application/json'
    return new Response(JSON.stringify(r.body ?? {}), { status: r.status, headers: { 'Content-Type': type } })
  })
  return seen
}

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })
}

beforeEach(() => {
  resetMemory()
  setScope('pyme-a')
  setAccessToken('tok')
  setOnline(true)
})
afterEach(() => {
  vi.restoreAllMocks()
  setOnline(true)
})

const movement = { path: '/stock/movements', body: { ingredient_id: 'i1', reason: 'purchase', delta_qty: '1' }, label: 'Sal: +1 kg' }

test('envía con Idempotency-Key y saca la operación de la cola', async () => {
  const seen = fakeFetch([{ status: 201 }])
  const op = await enqueue(movement)
  await flush()
  expect(seen).toEqual([{ path: '/stock/movements', key: op.id, body: movement.body }])
  expect(await pendingOps()).toEqual([])
})

test('sin red queda pendiente y al reintentar usa la MISMA clave (no duplica)', async () => {
  const seen = fakeFetch(['network', { status: 201 }])
  const op = await enqueue(movement)
  await flush()
  expect((await pendingOps()).map((o) => o.id)).toEqual([op.id])
  await flush()
  expect(seen.map((s) => s.key)).toEqual([op.id, op.id])
  expect(await pendingOps()).toEqual([])
})

test('con el teléfono offline ni siquiera intenta y respeta el orden al volver', async () => {
  setOnline(false)
  const seen = fakeFetch([])
  const a = await enqueue(movement)
  const b = await enqueue({ ...movement, label: 'Sal: -1 kg', body: { ...movement.body, delta_qty: '-1' } })
  await flush()
  expect(seen).toEqual([])
  setOnline(true)
  await flush()
  expect(seen.map((s) => s.key)).toEqual([a.id, b.id])
})

test('un error del servidor (5xx) se reintenta; un rechazo (4xx) pasa a fallidas con el motivo', async () => {
  fakeFetch([
    { status: 503 },
    { status: 422, body: { code: 'validation_error', title: 'Revisa los datos', detail: 'La cantidad no puede ser cero' } },
  ])
  const op = await enqueue(movement)
  await flush()
  expect((await pendingOps()).length).toBe(1)
  await flush()
  expect(await pendingOps()).toEqual([])
  const [failed] = await failedOps()
  expect(failed.id).toBe(op.id)
  expect(failed.error).toContain('La cantidad no puede ser cero')
  await dismissFailed(op.id)
  expect(await failedOps()).toEqual([])
})

test('con la sesión vencida la cola se conserva', async () => {
  fakeFetch([{ status: 401 }])
  await enqueue(movement)
  await flush()
  expect((await pendingOps()).length).toBe(1)
  expect(await failedOps()).toEqual([])
})

test('la cola y la caché son por pyme', async () => {
  setOnline(false)
  fakeFetch([])
  await enqueue(movement)
  setScope('pyme-b')
  expect(await pendingOps()).toEqual([])
  setScope('pyme-a')
  expect((await pendingOps()).length).toBe(1)
})

test('fetchCached: guarda con red, muestra lo guardado sin red y avisa si no hay nada', async () => {
  fakeFetch([{ status: 200, body: [{ id: 'i1', stock_qty: '3000.000' }] }])
  const fresh = await fetchCached<{ id: string; stock_qty: string }[]>('ingredients', '/ingredients')
  expect(fresh.fromCache).toBe(false)
  await patchCached<{ id: string; stock_qty: string }[]>('ingredients', (d) => d.map((i) => ({ ...i, stock_qty: '4000.000' })))
  setOnline(false)
  const cached = await fetchCached<{ id: string; stock_qty: string }[]>('ingredients', '/ingredients')
  expect(cached.fromCache).toBe(true)
  expect(cached.data[0].stock_qty).toBe('4000.000')
  await expect(fetchCached('recipes', '/recipes')).rejects.toMatchObject({ code: 'offline_no_cache' })
})
