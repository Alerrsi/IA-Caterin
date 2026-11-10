import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, inputClass } from '../components/ui'
import { t } from '../i18n'

export default function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ pyme: '', name: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register({
        pyme_name: form.pyme.trim(),
        full_name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
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
    <main className="mx-auto w-full max-w-md px-4 pb-16 pt-10">
      <h1 className="text-4xl font-bold text-brand">{t.appName}</h1>
      <h2 className="mb-6 mt-2 text-2xl font-bold text-stone-900">{t.register.title}</h2>
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
        {error && <Alert>{error}</Alert>}
        <Button type="submit" className="w-full" disabled={busy || !ready}>
          {busy ? t.register.submitting : t.register.submit}
        </Button>
      </form>
      <p className="mt-6 text-center">
        <a href="#/" className="inline-block min-h-12 py-3 text-lg font-semibold text-brand underline underline-offset-4">
          {t.register.toLogin}
        </a>
      </p>
    </main>
  )
}
