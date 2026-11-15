import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { t } from '../i18n'
import { dismissFailed, useQueue } from '../offline/queue'
import { Icon, type IconName } from './Icon'

/**
 * Componentes base sobre los roles de color de `index.css` (estética "plano de cocina", T16, ADR-010). Botones de
 * 48 px de alto mínimo (área táctil), esquina de 4 px, borde de tecla y foco visible; tarjetas y celdas con línea fina;
 * campos de texto delineados.
 */
type Variant = 'primary' | 'tonal' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  // La acción principal de la pantalla: tecla laurel con el borde inferior más oscuro.
  primary:
    'bg-primary text-on-primary shadow-key hover:bg-primary/92 active:shadow-key-pressed disabled:bg-on-surface/12 disabled:text-on-surface/40 disabled:shadow-none',
  // Acción importante pero no principal.
  tonal:
    'bg-secondary-container text-on-secondary-container hover:bg-secondary-container/80 disabled:bg-on-surface/12 disabled:text-on-surface/40',
  // Tecla clara: fondo blanco, borde fino y una sombra mínima.
  secondary:
    'border border-outline bg-surface-container-lowest text-on-surface shadow-cap hover:bg-surface-container-low disabled:border-on-surface/12 disabled:text-on-surface/40 disabled:shadow-none',
  // Acción de texto.
  ghost: 'bg-transparent text-primary hover:bg-primary/8 disabled:text-on-surface/40',
}

/**
 * Atajo de teclado visible (T16). Solo en escritorio con mouse; es decorativo porque el atajo se anuncia con
 * `aria-keyshortcuts` en el control.
 */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd
      aria-hidden="true"
      className="hidden h-6 min-w-6 items-center justify-center rounded-sm border border-current/30 px-1.5 font-mono text-sm leading-none opacity-80 pointer-fine:lg:inline-flex"
    >
      {children}
    </kbd>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  shortcut,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; shortcut?: string }) {
  return (
    <button
      type="button"
      aria-keyshortcuts={shortcut}
      className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-base font-medium transition-[background-color,box-shadow,translate] duration-150 ease-out focus:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 enabled:active:translate-y-px disabled:cursor-not-allowed motion-reduce:enabled:active:translate-y-0 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
      {shortcut && <Kbd>{shortcut}</Kbd>}
    </button>
  )
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'warning' | 'info'; children: ReactNode }) {
  const styles = {
    error: 'bg-error-container text-on-error-container',
    warning: 'bg-warning-container text-on-warning-container',
    info: 'bg-info-container text-on-info-container',
  }[kind]
  const icon = { error: 'error', warning: 'warning', info: 'info' }[kind] as IconName
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`flex gap-3 rounded-xl p-4 ${styles}`}>
      <Icon name={icon} className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

/**
 * Contenido de una pantalla dentro del marco de la app (`AppShell`): título en serif, bajada opcional y botón de volver.
 * `size="narrow"` para formularios de una columna; por defecto usa el ancho de escritorio.
 */
export function Page({
  title,
  description,
  onBack,
  children,
  size = 'wide',
  actions,
}: {
  title: string
  description?: ReactNode
  onBack?: () => void
  children: ReactNode
  size?: 'narrow' | 'wide'
  actions?: ReactNode
}) {
  return (
    <main
      className={`mx-auto w-full lg:min-h-dvh lg:border-x lg:border-hairline lg:bg-surface ${size === 'narrow' ? 'max-w-3xl' : 'max-w-6xl'}`}
    >
      {/* En escritorio la cabecera cruza los rieles del marco con una línea fina y marcas en los extremos (T16). */}
      <header className="flex items-start gap-2 px-4 pb-4 pt-4 md:px-8 md:pt-6 lg:frame-marks lg:border-b lg:border-hairline lg:pb-6">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="-ml-2 inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-on-surface/8 focus-visible:ring-4 focus-visible:ring-primary/30"
            aria-label={t.back}
          >
            <Icon name="back" className="h-6 w-6" />
          </button>
        )}
        <div className="min-w-0 flex-1 pt-1.5">
          <h1 className="text-[1.75rem] leading-9 text-on-surface md:text-[2.25rem] md:leading-11">{title}</h1>
          {description && <p className="mt-1 max-w-prose text-on-surface-variant">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 pt-1">{actions}</div>}
      </header>
      <div className="px-4 pb-24 pt-2 md:px-8 lg:pb-12 lg:pt-6">{children}</div>
    </main>
  )
}

/** Tarjeta con línea fina. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-hairline bg-surface-container-lowest p-4 md:p-5 ${className}`}>{children}</section>
}

/**
 * Grilla de celdas separadas por líneas de 1 px, sin espacio entre ellas (T16; utilidad `cells` en `index.css`).
 * Cada hijo debe ser un `<li>`.
 */
export function Cells({ children, className = '', label }: { children: ReactNode; className?: string; label?: string }) {
  return (
    <ul aria-label={label} className={`cells grid overflow-hidden rounded-xl border border-hairline bg-surface-container-lowest ${className}`}>
      {children}
    </ul>
  )
}

/** Cifra de comanda: cantidad, precio, código o fecha en monoespaciada con cifras tabulares (T16). */
export function Num({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`num ${className}`}>{children}</span>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-on-surface-variant">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-sm text-on-surface-variant">{hint}</span>}
    </label>
  )
}

// Campo delineado: esquina de 4 px, borde que se engrosa con el foco.
export const inputClass =
  'w-full min-h-12 rounded-md border border-outline bg-surface-container-lowest px-4 py-2 text-base text-on-surface placeholder:text-on-surface-variant/70 hover:border-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60'

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-3 text-on-surface-variant">
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-[3px] border-primary/20 border-t-primary" />
      {label}
    </p>
  )
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

/** Estado de la red y de la cola de cambios (ADR-004): siempre visible si hay algo que contar. */
export function OfflineBanner() {
  const online = useOnline()
  const { pending, failed } = useQueue()
  return (
    <>
      {(!online || pending.length > 0) && (
        <div role="status" className="border-b border-outline-variant bg-warning-container px-4 py-2 text-center text-on-warning-container">
          {!online && <span className="block">{t.offline}</span>}
          {pending.length > 0 && (
            <span className="block font-medium">
              {online ? t.sync.sending(pending.length) : t.sync.pending(pending.length)}
            </span>
          )}
        </div>
      )}
      {failed.length > 0 && (
        <div role="alert" className="bg-error-container px-4 py-3 text-on-error-container">
          <p className="font-medium">{t.sync.failed(failed.length)}</p>
          <ul className="mt-1 space-y-2">
            {failed.map((op) => (
              <li key={op.id} className="flex items-center justify-between gap-2">
                <span>
                  {op.label}: {op.error}
                </span>
                <button
                  type="button"
                  onClick={() => void dismissFailed(op.id)}
                  className="min-h-12 shrink-0 rounded-lg px-4 font-medium transition-colors hover:bg-on-error-container/8 focus-visible:ring-4 focus-visible:ring-error/40"
                >
                  {t.sync.dismiss}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

/** Estado de un pedido o cotización: etiqueta con el color del estado y esquina de 2 px. */
export function StatusChip({ status, children }: { status: string; children: ReactNode }) {
  const tone =
    status === 'confirmed' || status === 'accepted' || status === 'delivered'
      ? 'bg-success-container text-on-success-container'
      : status === 'cancelled' || status === 'rejected'
        ? 'bg-surface-container-highest text-on-surface-variant'
        : status === 'requested' || status === 'sent'
          ? 'bg-info-container text-on-info-container'
          : 'bg-secondary-container text-on-secondary-container'
  return (
    <span className={`inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-sm px-2.5 text-sm font-medium ${tone}`}>
      {children}
    </span>
  )
}
