import { useEffect, useRef } from 'react'

/**
 * Atajos de teclado de una sola tecla (T16, ADR-010). Pensados para escritorio; en el celular no estorban porque el
 * teclado en pantalla solo aparece dentro de un campo, donde el atajo no actúa.
 * - No actúan si se escribe en un campo, si hay Ctrl, Alt o Cmd presionado, ni si la tecla se mantiene apretada.
 * - El control que dispara la acción debe declarar `aria-keyshortcuts` para los lectores de pantalla.
 */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

export function useShortcut(key: string, action: () => void, enabled = true): void {
  const ref = useRef(action)
  useEffect(() => {
    ref.current = action
  })
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || isTyping(e.target)) return
      if (e.key.toLowerCase() !== key.toLowerCase()) return
      // Un diálogo modal abierto tiene prioridad (el cajón del celular, por ejemplo).
      if (document.querySelector('[aria-modal="true"]')) return
      e.preventDefault()
      ref.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [key, enabled])
}
