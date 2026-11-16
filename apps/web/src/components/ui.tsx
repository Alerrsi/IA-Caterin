import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { t } from '../i18n'
import { dismissFailed, useQueue } from '../offline/queue'
import { Icon, type IconName } from './Icon'

/**
 * Componentes base sobre los roles de color de `index.css` (T21, ADR-013: estética de la imagen de referencia). Botones
 * en píldora de 48 px mínimo (área táctil) con sombra suave y foco visible; tarjetas blancas redondeadas con sombra
 * difusa; campos redondeados.
 */
type Variant = 'primary' | 'tonal' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  // La acción principal de la pantalla: píldora negra con texto blanco.
  primary:
    'bg-primary text-on-primary shadow-key hover:bg-primary/88 active:shadow-key-pressed disabled:bg-on-surface/12 disabled:text-on-surface/40 disabled:shadow-none',
  // Acción importante pero no principal: píldora amarilla con texto negro (el amarillo solo es fondo).
  tonal:
    'bg-accent text-on-accent shadow-cap hover:bg-accent/85 disabled:bg-on-surface/12 disabled:text-on-surface/40 disabled:shadow-none',
  // Píldora clara delineada (como "Sign In" de la referencia).
  secondary:
    'border border-outline bg-surface-container-lowest text-on-surface hover:bg-surface-container-low disabled:border-on-surface/12 disabled:text-on-surface/40',
  // Acción de texto.
  ghost: 'bg-transparent text-primary underline-offset-4 hover:bg-primary/6 hover:underline disabled:text-on-surface/40',
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

/**
 * Botón en píldora. Con `icon`, el ícono va dentro de un círculo amarillo al inicio, como el "Buy Now" de la
 * referencia (en el botón amarillo el círculo es negro).
 */
export function Button({
  variant = 'primary',
  className = '',
  shortcut,
  icon,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; shortcut?: string; icon?: IconName }) {
  return (
    <button
      type="button"
      aria-keyshortcuts={shortcut}
      className={`inline-flex min-h-12 items-center justify-center gap-3 rounded-lg py-2.5 text-base font-semibold transition-[background-color,box-shadow,translate] duration-150 ease-out focus:outline-none focus-visible:ring-4 focus-visible:ring-accent enabled:active:translate-y-px disabled:cursor-not-allowed motion-reduce:enabled:active:translate-y-0 ${icon ? 'pl-1.5 pr-6' : 'px-6'} ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {icon && <IconDot name={icon} dark={variant === 'tonal'} />}
      {children}
      {shortcut && <Kbd>{shortcut}</Kbd>}
    </button>
  )
}

/** Círculo con un ícono: amarillo con ícono negro (o negro con ícono amarillo sobre fondos amarillos). Decorativo. */
export function IconDot({ name, dark = false, className = '' }: { name: IconName; dark?: boolean; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${dark ? 'bg-primary text-accent' : 'bg-accent text-on-accent'} ${className}`}
    >
      <Icon name={name} className="h-5 w-5" />
    </span>
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
 * Contenido de una pantalla dentro del marco de la app (`AppShell`): título grande en dos pesos, bajada opcional y
 * botón de volver. `lead` va arriba en peso normal y `title` abajo en negrita ("Mi / negocio"), como los títulos de la
 * referencia. `size="narrow"` para formularios de una columna; por defecto usa el ancho de escritorio.
 */
export function Page({
  title,
  lead,
  description,
  onBack,
  children,
  size = 'wide',
  actions,
}: {
  title: string
  lead?: string
  description?: ReactNode
  onBack?: () => void
  children: ReactNode
  size?: 'narrow' | 'wide'
  actions?: ReactNode
}) {
  return (
    <main className={`mx-auto w-full ${size === 'narrow' ? 'max-w-3xl' : 'max-w-6xl'}`}>
      <header className="flex items-start gap-2 px-4 pb-4 pt-5 md:px-8 md:pt-8 lg:pb-6">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="-ml-1 mt-1 inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-container-lowest text-on-surface shadow-cap transition-colors hover:bg-accent focus-visible:ring-4 focus-visible:ring-accent"
            aria-label={t.back}
          >
            <Icon name="back" className="h-6 w-6" />
          </button>
        )}
        <div className="min-w-0 flex-1 pt-1 md:pl-2">
          <h1 className="text-[2rem] leading-10 text-on-surface md:text-[2.75rem] md:leading-[3.25rem]">
            {lead && <span className="block font-normal">{lead}</span>}
            {title}
          </h1>
          {description && <p className="mt-2 max-w-prose text-on-surface-variant">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 pt-2">{actions}</div>}
      </header>
      <div className="px-4 pb-28 pt-2 md:px-8 lg:pb-16 lg:pt-4">{children}</div>
    </main>
  )
}

/** Tarjeta blanca redondeada con sombra difusa. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl bg-surface-container-lowest p-4 shadow-cap md:p-6 ${className}`}>{children}</section>
}

/**
 * Grilla de tarjetas con aire entre ellas (utilidad `cells` en `index.css`: cada hijo es una tarjeta blanca con
 * sombra suave). Cada hijo debe ser un `<li>`.
 */
export function Cells({ children, className = '', label }: { children: ReactNode; className?: string; label?: string }) {
  return (
    <ul aria-label={label} className={`cells grid gap-3 md:gap-4 ${className}`}>
      {children}
    </ul>
  )
}

/** Cifra: cantidad, precio, código o fecha, con cifras tabulares y peso firme. */
export function Num({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`num ${className}`}>{children}</span>
}

/** Píldora pequeña de información (como "30 dk." de la referencia): fondo amarillo, texto negro. */
export function Pill({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-semibold text-on-accent ${className}`}>
      {children}
    </span>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-on-surface">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-sm text-on-surface-variant">{hint}</span>}
    </label>
  )
}

// Campo redondeado: fondo blanco, borde que se vuelve negro con el foco y aro amarillo.
export const inputClass =
  'w-full min-h-12 rounded-md border border-outline bg-surface-container-lowest px-4 py-2 text-base text-on-surface placeholder:text-on-surface-variant/70 hover:border-on-surface focus:border-primary focus:outline-none focus:ring-4 focus:ring-accent/60 disabled:opacity-60'

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-3 text-on-surface-variant">
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-[3px] border-accent/40 border-t-primary" />
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

/** Estado de un pedido o cotización: píldora con el color del estado. */
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
    <span className={`inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-lg px-3 text-sm font-semibold ${tone}`}>
      {children}
    </span>
  )
}
