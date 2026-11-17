/**
 * "Seguir donde quedaste" (T22): los últimos elementos abiertos (insumo, receta, cotización), guardados solo en este
 * teléfono y por persona. Si el almacenamiento no está disponible (modo privado, bloqueado), no pasa nada: la app
 * funciona igual, solo no muestra la lista.
 */
import { useEffect, useSyncExternalStore } from 'react'
import { useAuth } from './auth'

export interface RecentItem {
  path: string
  label: string
  kind: 'ingredient' | 'recipe' | 'quote' | 'pyme'
}

export const MAX_RECENT = 3
const EMPTY: RecentItem[] = []
const listeners = new Set<() => void>()
const memo = new Map<string, { raw: string | null; items: RecentItem[] }>()

function key(userId: string): string {
  return `caterin:recent:${userId}`
}

function read(userId: string): RecentItem[] {
  let raw: string | null
  try {
    raw = window.localStorage.getItem(key(userId))
  } catch {
    return EMPTY
  }
  const cached = memo.get(userId)
  if (cached && cached.raw === raw) return cached.items
  let items: RecentItem[] = []
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : []
    if (Array.isArray(parsed)) {
      items = parsed
        .filter((i): i is RecentItem => typeof i?.path === 'string' && typeof i?.label === 'string')
        .slice(0, MAX_RECENT)
    }
  } catch {
    items = []
  }
  memo.set(userId, { raw, items })
  return items
}

/** Agrega `item` al principio (sin repetir la misma ruta) y conserva los últimos `MAX_RECENT`. */
export function remember(userId: string | undefined, item: RecentItem): void {
  if (!userId) return
  const next = [item, ...read(userId).filter((i) => i.path !== item.path)].slice(0, MAX_RECENT)
  try {
    window.localStorage.setItem(key(userId), JSON.stringify(next))
  } catch {
    return
  }
  listeners.forEach((l) => l())
}

export function recentFor(userId: string | undefined): RecentItem[] {
  return userId ? read(userId) : EMPTY
}

export function useRecent(userId: string | undefined): RecentItem[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => recentFor(userId),
    () => EMPTY,
  )
}

/** Recuerda la pantalla abierta (insumo, receta, cotización o pyme) cuando ya tiene nombre. */
export function useRemember(item: RecentItem | null): void {
  const { user } = useAuth()
  const userId = user?.id
  const path = item?.path
  const label = item?.label
  const kind = item?.kind
  useEffect(() => {
    if (path && label && kind) remember(userId, { path, label, kind })
  }, [userId, path, label, kind])
}
