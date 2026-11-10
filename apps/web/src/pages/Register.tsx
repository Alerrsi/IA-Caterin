import { useState, type FormEvent } from 'react'
import { ApiError, patch } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, inputClass } from '../components/ui'
import { parseQtyInput } from '../format'
import { t } from '../i18n'

export default function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ pyme: '', name: '', email: '', password: '', margin: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    // Margen opcional: sin él no se puede cotizar, pero no se inventa un valor por defecto.
    const margin = form.margin.trim() ? parseQtyInput(form.margin) : null
    if (form.margin.trim() && (margin === null || !(Number(margin) >= 0 && Number(margin) <= 100))) {
      return setError(t.register.badMargin)
    }
    setBusy(true)
    try {
      await register({
        pyme_name: form.pyme.trim(),
        full_name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      if (margin !== null) await patch('/pyme', { default_margin_pct: margin }).catch(() => undefined)
      window.location.hash = '#/'
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  const ready =
    form.pyme.trim().length >= 2 && form.name.trim().length >= 2 && form.email.includes('@') && form.password.length >= 10

  return (
    <main className="flex min-h-dvh items-start justify-center bg-surface-container px-4 py-10 md:items-center">
      <div className="w-full max-w-md rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 md:p-10">
      <h1 className="text-3xl font-normal text-on-surface">{t.appName}</h1>
      <h2 className="mb-6 mt-2 text-2xl font-medium text-on-surface">{t.register.title}</h2>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label={t.register.pyme}>
          <input className={inputClass} autoComplete="organization" value={form.pyme} onChange={set('pyme')} />
        </Field>
        <Field label={t.register.name}>
          <input className={inputClass} autoComplete="name" value={form.name} onChange={set('name')} />
        </Field>
        <Field label={t.register.email}>
          <input
            className={inputClass}
            type="email"
            inputMode="email"
            autoComplete="username"
            value={form.email}
            onChange={set('email')}
          />
        </Field>
        <Field label={t.register.password}>
          <input
            className={inputClass}
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={set('password')}
          />
        </Field>
        <Field label={t.register.margin} hint={t.register.marginHint}>
          <input className={inputClass} inputMode="decimal" value={form.margin} onChange={set('margin')} />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" className="w-full" disabled={busy || !ready}>
          {busy ? t.register.submitting : t.register.submit}
        </Button>
      </form>
      <p className="mt-6 text-center">
        <a href="#/" className="inline-block min-h-12 py-3 text-lg font-medium text-primary underline underline-offset-4">
          {t.register.toLogin}
        </a>
      </p>
    </div>
    </main>
  )
}
