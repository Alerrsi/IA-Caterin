import { useState, type FormEvent } from 'react'
import { ApiError, patch } from '../api'
import { useAuth } from '../auth'
import { parseQtyInput } from '../format'
import { t } from '../i18n'
import { Alert, Button, Field, inputClass } from './ui'

/** true si la API rechazó la cotización porque la pyme no tiene margen definido (422 margin_required). */
export function isMarginRequired(err: unknown): boolean {
  return err instanceof ApiError && err.code === 'margin_required'
}

/**
 * Formulario en línea para fijar el margen y reintentar la cotización con un toque.
 * No sugiere un valor: el margen es una decisión de negocio de la dueña.
 */
export function MarginFix({ onSaved }: { onSaved: () => void | Promise<void> }) {
  const { user } = useAuth()
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user?.role !== 'owner') return <Alert kind="warning">{t.marginFix.ownerOnly}</Alert>

  async function submit(e: FormEvent) {
    e.preventDefault()
    const parsed = parseQtyInput(value)
    const n = parsed === null ? NaN : Number(parsed)
    if (!(n >= 0 && n <= 100)) return setError(t.marginFix.bad)
    setBusy(true)
    setError(null)
    try {
      await patch('/pyme', { default_margin_pct: parsed })
      await onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border-l-4 border-amber-600 bg-amber-50 p-4" noValidate>
      <p className="font-bold text-amber-950">{t.marginFix.title}</p>
      <p className="text-amber-950">{t.marginFix.body}</p>
      <Field label={t.marginFix.label}>
        <input className={inputClass} inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
      </Field>
      {error && <Alert>{error}</Alert>}
      <Button type="submit" className="w-full" disabled={busy || !value.trim()}>
        {busy ? t.marginFix.saving : t.marginFix.save}
      </Button>
    </form>
  )
}
