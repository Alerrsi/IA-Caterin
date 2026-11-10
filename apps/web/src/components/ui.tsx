import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { t } from '../i18n'
import { dismissFailed, useQueue } from '../offline/queue'
import { Icon, type IconName } from './Icon'

/**
 * Componentes base con Material Design 3 (esquema neutro de `index.css`). Botones de 48 px de alto mínimo (área
 * táctil), forma de píldora y foco visible; tarjetas delineadas; campos de texto delineados.
 */
type Variant = 'primary' | 'tonal' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  // MD3 "filled": la acción principal de la pantalla.
  primary:
    'bg-primary text-on-primary hover:bg-primary/90 hover:shadow-sm disabled:bg-on-surface/12 disabled:text-on-surface/40 disabled:shadow-none',
  // MD3 "filled tonal": acción importante pero no principal.
  tonal: 'bg-secondary-container text-on-secondary-container hover:shadow-sm disabled:bg-on-surface/12 disabled:text-on-surface/40',
  // MD3 "outlined".
  secondary:
    'border border-outline bg-transparent text-primary hover:bg-primary/8 disabled:border-on-surface/12 disabled:text-on-surface/40',
  // MD3 "text".
  ghost: 'bg-transparent text-primary hover:bg-primary/8 disabled:text-on-surface/40',
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-full px-6 py-2.5 text-base font-medium tracking-wide transition focus:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
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
 * Contenido de una pantalla dentro del marco de la app (`AppShell`): título MD3 y botón de volver.
 * `size="narrow"` para formularios de una columna; por defecto usa el ancho de escritorio.
 */
export function Page({
  title,
  onBack,
  children,
  size = 'wide',
  actions,
}: {
  title: string
  onBack?: () => void
  children: ReactNode
  size?: 'narrow' | 'wide'
  actions?: ReactNode
}) {
  return (
    <main className={`mx-auto w-full px-4 pb-24 pt-4 md:px-8 md:pt-6 lg:pb-12 ${size === 'narrow' ? 'max-w-3xl' : 'max-w-6xl'}`}>
      <header className="mb-6 flex items-center gap-2">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="-ml-2 inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface-variant hover:bg-on-surface/8 focus-visible:ring-4 focus-visible:ring-primary/30"
            aria-label={t.back}
          >
            <Icon name="back" className="h-6 w-6" />
          </button>
        )}
        <h1 className="flex-1 text-2xl font-normal text-on-surface md:text-[2rem] md:leading-10">{title}</h1>
        {actions}
      </header>
      {children}
    </main>
  )
}

/** Tarjeta MD3 delineada. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-outline-variant bg-surface-container-lowest p-4 md:p-5 ${className}`}>{children}</section>
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

// MD3 "outlined text field": esquina de 4 px, borde que se engrosa con el foco.
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
        <div role="status" className="bg-inverse-surface px-4 py-2 text-center text-inverse-on-surface">
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
                  className="min-h-12 shrink-0 rounded-full px-4 font-medium hover:bg-on-error-container/8 focus-visible:ring-4 focus-visible:ring-error/40"
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

/** Estado de un pedido o cotización: chip MD3 con el color del estado. */
export function StatusChip({ status, children }: { status: string; children: ReactNode }) {
  const tone =
    status === 'confirmed' || status === 'accepted' || status === 'delivered'
      ? 'bg-success-container text-on-success-container'
      : status === 'cancelled' || status === 'rejected'
        ? 'bg-surface-container-highest text-on-surface-variant'
        : status === 'requested' || status === 'sent'
          ? 'bg-info-container text-on-info-container'
          : 'bg-secondary-container text-on-secondary-container'
  return <span className={`inline-flex h-8 items-center rounded-lg px-3 text-sm font-medium ${tone}`}>{children}</span>
}
