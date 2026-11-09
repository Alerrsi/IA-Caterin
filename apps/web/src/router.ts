/** Router mínimo por hash (#/ruta): funciona sin servidor y offline en la PWA. */
import { useEffect, useState } from 'react'

export function currentPath(): string {
  const hash = window.location.hash.replace(/^#/, '')
  return hash || '/'
}

export function navigate(path: string): void {
  window.location.hash = path
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
