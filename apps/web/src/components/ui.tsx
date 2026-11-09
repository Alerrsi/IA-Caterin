import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { t } from '../i18n'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-dark disabled:bg-stone-400',
  secondary: 'bg-white text-brand border-2 border-brand hover:bg-orange-50 disabled:text-stone-500 disabled:border-stone-300',
  ghost: 'text-brand underline underline-offset-4 hover:text-brand-dark',
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`min-h-12 rounded-xl px-4 py-3 text-lg font-semibold focus:outline-none focus-visible:ring-4 focus-visible:ring-orange-300 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'warning' | 'info'; children: ReactNode }) {
  const styles = {
    error: 'border-red-700 bg-red-50 text-red-900',
    warning: 'border-amber-600 bg-amber-50 text-amber-950',
    info: 'border-sky-700 bg-sky-50 text-sky-950',
  }[kind]
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded-xl border-l-4 p-4 ${styles}`}>
      {children}
    </div>
  )
}

export function Page({ title, onBack, children }: { title: string; onBack?: () => void; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-xl px-4 pb-16 pt-4">
      <header className="mb-4 flex items-center gap-2">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="min-h-12 min-w-12 rounded-xl text-2xl text-brand focus-visible:ring-4 focus-visible:ring-orange-300"
            aria-label={t.back}
          >
            ←
          </button>
        )}
        <h1 className="text-2xl font-bold text-brand">{title}</h1>
      </header>
      {children}
    </main>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block font-semibold text-stone-800">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-sm text-stone-600">{hint}</span>}
    </label>
  )
}

export const inputClass =
  'w-full min-h-12 rounded-xl border-2 border-stone-300 bg-white px-3 py-2 text-lg focus:border-brand focus:outline-none'

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-3 text-stone-700">
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-4 border-orange-200 border-t-brand" />
      {label}
    </p>
  )
}

export function OfflineBanner() {
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
  if (online) return null
  return (
    <div role="status" className="bg-stone-900 px-4 py-2 text-center text-white">
      {t.offline}
    </div>
  )
}
