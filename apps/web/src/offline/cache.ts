/** Catálogos con *stale-while-revalidate* (ADR-004): se pide a la red y, si no hay, se muestra lo guardado. */
import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api'
import { getItem, setItem } from './db'

interface Stored<T> {
  data: T
  savedAt: string
}

export interface Cached<T> extends Stored<T> {
  fromCache: boolean
}

function offline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

/** `source`: una ruta GET de la API o una función que arma el dato (p. ej. juntando páginas). */
export async function fetchCached<T>(name: string, source: string | (() => Promise<T>)): Promise<Cached<T>> {
  if (!offline()) {
    try {
      const data = typeof source === 'string' ? await api<T>(source) : await source() // ETag: lo revalida el navegador
      const stored = { data, savedAt: new Date().toISOString() }
      await setItem(`cache:${name}`, stored)
      return { ...stored, fromCache: false }
    } catch (err) {
      if (!(err instanceof ApiError) || err.status !== 0) throw err
    }
  }
  const hit = await getItem<Stored<T>>(`cache:${name}`)
  if (hit) return { ...hit, fromCache: true }
  throw new ApiError(0, 'offline_no_cache', 'Sin conexión', 'Todavía no hay datos guardados en este teléfono.')
}

/** Cambia lo guardado (p. ej. el stock tras un ajuste encolado) sin esperar a la red. */
export async function patchCached<T>(name: string, fn: (data: T) => T): Promise<void> {
  const hit = await getItem<Stored<T>>(`cache:${name}`)
  if (hit) await setItem(`cache:${name}`, { ...hit, data: fn(hit.data) })
}

export function useCached<T>(name: string, path: string | (() => Promise<T>) | null) {
  const [state, setState] = useState<{ value: Cached<T> | null; error: ApiError | null; loading: boolean }>({
    value: null,
    error: null,
    loading: path !== null,
  })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (path === null) return
    let alive = true
    fetchCached<T>(name, path).then(
      (value) => alive && setState({ value, error: null, loading: false }),
      (err: unknown) => {
        const e = err instanceof ApiError ? err : new ApiError(0, 'error', String(err))
        if (alive) setState((s) => ({ ...s, error: e, loading: false }))
      },
    )
    return () => {
      alive = false
    }
  }, [name, path, tick])
  /** Vuelve a pedir el dato (p. ej. cuando la cola terminó de enviar). */
  const reload = useCallback(() => {
    setState((s) => ({ ...s, loading: true }))
    setTick((n) => n + 1)
  }, [])
  /** Cambio optimista: en pantalla y en lo guardado, sin esperar a la red. */
  const setData = useCallback(
    (fn: (d: T) => T) => {
      setState((s) => (s.value ? { ...s, value: { ...s.value, data: fn(s.value.data) } } : s))
      void patchCached<T>(name, fn)
    },
    [name],
  )
  return { ...state, reload, setData }
}
