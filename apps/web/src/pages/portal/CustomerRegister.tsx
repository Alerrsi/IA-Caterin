import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../../api'
import { useAuth } from '../../auth'
import { Alert, Button, Field, inputClass, Spinner } from '../../components/ui'
import { t } from '../../i18n'
import { navigate } from '../../router'

/** Registro de un cliente con el enlace que comparte la pyme (#/cliente/<código>). */
export default function CustomerRegister({ code }: { code: string }) {
  const { registerCustomer } = useAuth()
  const [pyme, setPyme] = useState<{ name: string } | null>(null)
  const [badLink, setBadLink] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  useEffect(() => {
    api<{ name: string }>(`/portal/pymes/${encodeURIComponent(code)}`)
      .then(setPyme)
      .catch(() => setBadLink(true))
  }, [code])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await registerCustomer({ code, full_name: form.name.trim(), email: form.email.trim(), password: form.password })
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-start justify-center bg-surface-container px-4 py-10 md:items-center">
      <div className="w-full max-w-md rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 md:p-10">
      <h1 className="text-2xl font-normal text-on-surface">{t.portal.registerTitle}</h1>
      {badLink ? (
        <div className="mt-6">
          <Alert>{t.portal.badLink}</Alert>
        </div>
      ) : !pyme ? (
        <Spinner label={t.loading} />
      ) : (
        <>
          <p className="mb-6 mt-1 text-on-surface-variant">{t.portal.registerFor(pyme.name)}</p>
          <form onSubmit={submit} className="space-y-4" noValidate>
            <Field label={t.register.name}>
              <input className={inputClass} value={form.name} onChange={set('name')} autoComplete="name" required />
            </Field>
            <Field label={t.register.email}>
              <input
                className={inputClass}
                type="email"
                inputMode="email"
                autoComplete="username"
                value={form.email}
                onChange={set('email')}
                required
              />
            </Field>
            <Field label={t.register.password}>
              <input
                className={inputClass}
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={set('password')}
                required
              />
            </Field>
            {error && <Alert>{error}</Alert>}
            <Button
              type="submit"
              className="w-full"
              disabled={busy || form.name.trim().length < 2 || !form.email || form.password.length < 10}
            >
              {busy ? t.register.submitting : t.register.submit}
            </Button>
          </form>
        </>
      )}
      <p className="mt-6 text-center">
        <a href="#/" className="inline-block min-h-12 py-3 text-lg font-medium text-primary underline underline-offset-4">
          {t.register.toLogin}
        </a>
      </p>
    </div>
    </main>
  )
}
