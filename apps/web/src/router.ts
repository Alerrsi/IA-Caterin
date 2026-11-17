/** Router mínimo por hash (#/ruta): funciona sin servidor y offline en la PWA. */
import { useEffect, useState } from 'react'

export function currentPath(): string {
  const hash = window.location.hash.replace(/^#/, '')
  return hash || '/'
}

let replacing = false

/**
 * Cambia de pantalla. Con `replace`, la nueva reemplaza a la actual en el historial: después de guardar un formulario
 * (nuevo insumo, nueva receta, cotizar), "Volver" no regresa al formulario ya enviado (T22).
 */
export function navigate(path: string, options: { replace?: boolean } = {}): void {
  if (options.replace) {
    // Si ya se está en esa ruta no hay `hashchange`: no se marca, o la próxima visita reemplazaría en vez de sumar.
    if (currentPath() === path) return
    replacing = true
    window.location.replace(`#${path}`)
  } else {
    window.location.hash = path
  }
}

/**
 * Historial propio de la sesión (T22): sabe si "Volver" puede regresar a una pantalla de la app o si se entró directo
 * por un enlace (ahí `history.back()` sacaría a la usuaria de la app). Solo guarda rutas, en memoria.
 */
const trail: string[] = []

function pathOnly(path: string): string {
  return path.split('?')[0] || '/'
}

/** Registra el cambio de pantalla: si se volvió a la anterior, la saca del rastro; si no, la agrega. */
export function recordVisit(path: string): void {
  if (replacing) {
    replacing = false
    trail[trail.length - 1] = path
    return
  }
  const last = trail[trail.length - 1]
  if (last === path) return
  if (trail.length > 1 && trail[trail.length - 2] === path) trail.pop()
  else trail.push(path)
  if (trail.length > 50) trail.shift()
}

/** Para las pruebas. */
export function resetTrail(path = currentPath()): void {
  trail.length = 0
  trail.push(path)
}

if (typeof window !== 'undefined') {
  resetTrail()
  window.addEventListener('hashchange', () => recordVisit(currentPath()))
}

/**
 * Volver (T22): a la pantalla anterior de la app si existe; si se entró directo, al padre lógico (`fallback`).
 * Así, de una receta abierta desde un pedido se vuelve al pedido, y no siempre al inicio.
 */
export function goBack(fallback: string): void {
  const here = pathOnly(currentPath())
  const previous = trail.length > 1 ? trail[trail.length - 2] : null
  if (previous !== null && pathOnly(previous) !== here) window.history.back()
  else navigate(fallback)
}

export function useHashPath(): string {
  const [path, setPath] = useState(currentPath)
  useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return path
}

/** Parámetros de la ruta actual: "/inventario?bajo=1" -> URLSearchParams con bajo=1. */
export function queryParams(path = currentPath()): URLSearchParams {
  const i = path.indexOf('?')
  return new URLSearchParams(i >= 0 ? path.slice(i + 1) : '')
}

/**
 * Cambia los filtros de la ruta actual sin crear una entrada nueva en el historial ni volver a renderizar la pantalla
 * (la pantalla ya tiene el estado; la URL queda para recargar, guardar o compartir la vista filtrada).
 */
export function replaceQuery(params: Record<string, string | null>): void {
  const path = currentPath()
  const base = pathOnly(path)
  const q = queryParams(path)
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === '') q.delete(k)
    else q.set(k, v)
  }
  const text = q.toString()
  const next = `#${base}${text ? `?${text}` : ''}`
  if (next !== window.location.hash) window.history.replaceState(window.history.state, '', next)
  trail[trail.length - 1] = next.slice(1)
}

/** "/cotizaciones/:id" contra "/cotizaciones/abc" -> { id: "abc" } */
export function matchPath(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split('/').filter(Boolean)
  const actual = path.split('?')[0].split('/').filter(Boolean)
  if (p.length !== actual.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(actual[i])
    else if (p[i] !== actual[i]) return null
  }
  return params
}
