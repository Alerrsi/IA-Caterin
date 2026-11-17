import { useEffect, useRef, type ReactNode, type RefObject } from 'react'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Diálogo modal accesible (T22): foco atrapado, Esc y toque fuera cierran, y al cerrar el foco vuelve a donde estaba.
 * `placement="sheet"` sube desde abajo en el celular (hoja) y se muestra como panel en escritorio; `"top"` es un panel
 * arriba (buscador). Estética T21: tarjeta blanca de esquinas generosas y sombra difusa.
 */
export function Dialog({
  label,
  onClose,
  children,
  placement = 'sheet',
  initialFocus,
  className = '',
}: {
  label: string
  onClose: () => void
  children: ReactNode
  placement?: 'sheet' | 'top'
  initialFocus?: RefObject<HTMLElement | null>
  className?: string
}) {
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  })

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const first = initialFocus?.current ?? panel.current?.querySelector<HTMLElement>(FOCUSABLE) ?? panel.current
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        close.current()
        return
      }
      if (e.key !== 'Tab' || !panel.current) return
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.closest('[hidden]'))
      if (items.length === 0) return
      const firstEl = items[0]
      const lastEl = items[items.length - 1]
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault()
        lastEl.focus()
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault()
        firstEl.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      if (previous && document.contains(previous)) previous.focus()
    }
    // Solo al abrir y cerrar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const position =
    placement === 'sheet'
      ? 'inset-x-0 bottom-0 max-h-[85dvh] rounded-t-3xl pb-[calc(env(safe-area-inset-bottom)+1rem)] starting:translate-y-8 lg:inset-x-auto lg:bottom-auto lg:right-6 lg:top-24 lg:w-[440px] lg:rounded-3xl lg:pb-4'
      : 'inset-x-3 top-3 max-h-[80dvh] rounded-3xl starting:-translate-y-4 md:left-1/2 md:right-auto md:top-20 md:w-[600px] md:-translate-x-1/2'

  return (
    <div className="fixed inset-0 z-50">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-black/45 transition-opacity duration-200 ease-out starting:opacity-0 motion-reduce:transition-none"
        onClick={onClose}
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={`absolute flex flex-col overflow-hidden bg-surface-container-lowest shadow-soft outline-none transition-[translate,opacity] duration-200 ease-out starting:opacity-0 motion-reduce:transition-none ${position} ${className}`}
      >
        {children}
      </div>
    </div>
  )
}
