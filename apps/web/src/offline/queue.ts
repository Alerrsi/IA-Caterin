/**
 * Cola de escrituras sin conexión (ADR-004). Cada operación lleva un id que viaja como `Idempotency-Key`:
 * si se envía dos veces (la red se cortó después de guardar), la API devuelve el original sin duplicar.
 * Se envía al volver la red, al abrir la app y cada 30 s mientras haya pendientes. Si la API rechaza una
 * operación (4xx), pasa a "fallidas" con el motivo para que la usuaria la vea; no se reintenta sola.
 */
import { useEffect, useState } from 'react'
import { ApiError, raw } from '../api'
import { getItem, setItem, uuid } from './db'

export interface QueuedOp {
  id: string
  path: string
  body: unknown
  label: string
  createdAt: string
  error?: string
}

const PENDING = 'queue:pending'
const FAILED = 'queue:failed'
const listeners = new Set<() => void>()
let flushing: Promise<number> | null = null

function notify(): void {
  listeners.forEach((fn) => fn())
}

export async function pendingOps(): Promise<QueuedOp[]> {
  return (await getItem<QueuedOp[]>(PENDING)) ?? []
}

export async function failedOps(): Promise<QueuedOp[]> {
  return (await getItem<QueuedOp[]>(FAILED)) ?? []
}

export async function enqueue(op: { path: string; body: unknown; label: string }): Promise<QueuedOp> {
  const item: QueuedOp = { id: uuid(), createdAt: new Date().toISOString(), ...op }
  await setItem(PENDING, [...(await pendingOps()), item])
  notify()
  void flush()
  return item
}

export async function dismissFailed(id: string): Promise<void> {
  await setItem(FAILED, (await failedOps()).filter((o) => o.id !== id))
  notify()
}

async function flushOnce(): Promise<number> {
  let sent = 0
  for (;;) {
    const [op] = await pendingOps()
    if (!op || (typeof navigator !== 'undefined' && navigator.onLine === false)) break
    try {
      await raw(op.path, { method: 'POST', body: JSON.stringify(op.body), headers: { 'Idempotency-Key': op.id } })
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0
      const permanent = status >= 400 && status < 500 && ![401, 408, 429].includes(status)
      if (!permanent) break // sin red, sesión vencida o error del servidor: se reintenta después
      const message = err instanceof ApiError ? err.userMessage : String(err)
      await setItem(FAILED, [...(await failedOps()), { ...op, error: message }])
    }
    await setItem(PENDING, (await pendingOps()).filter((o) => o.id !== op.id))
    sent += 1
    notify()
  }
  return sent
}

/** Envía lo pendiente, en orden. Devuelve cuántas operaciones salieron de la cola. */
export function flush(): Promise<number> {
  if (!flushing) flushing = flushOnce().finally(() => (flushing = null))
  return flushing
}

export function startSync(intervalMs = 30_000): () => void {
  const onOnline = () => void flush()
  window.addEventListener('online', onOnline)
  const timer = window.setInterval(() => void flush(), intervalMs)
  void flush()
  return () => {
    window.removeEventListener('online', onOnline)
    window.clearInterval(timer)
  }
}

export function useQueue(): { pending: QueuedOp[]; failed: QueuedOp[] } {
  const [state, setState] = useState<{ pending: QueuedOp[]; failed: QueuedOp[] }>({ pending: [], failed: [] })
  useEffect(() => {
    let alive = true
    const refresh = async () => {
      const [pending, failed] = await Promise.all([pendingOps(), failedOps()])
      if (alive) setState({ pending, failed })
    }
    listeners.add(refresh)
    void refresh()
    return () => {
      alive = false
      listeners.delete(refresh)
    }
  }, [])
  return state
}
