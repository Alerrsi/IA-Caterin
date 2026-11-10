import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, inputClass } from '../components/ui'
import { t } from '../i18n'

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-start justify-center bg-surface-container px-4 py-10 md:items-center">
      <div className="w-full max-w-md rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 md:p-10">
      <h1 className="text-3xl font-normal text-on-surface">{t.appName}</h1>
      <p className="mb-8 mt-1 text-on-surface-variant">{t.tagline}</p>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label={t.login.email}>
          <input
            className={inputClass}
            type="email"
            autoComplete="username"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label={t.login.password}>
          <input
            className={inputClass}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>
          {busy ? t.login.submitting : t.login.submit}
        </Button>
      </form>
      <p className="mt-6 text-center">
        <a href="#/registro" className="inline-block min-h-12 py-3 text-lg font-medium text-primary underline underline-offset-4">
          {t.register.link}
        </a>
      </p>
      <p className="text-center">
        <a href="#/cliente" className="inline-block min-h-12 py-3 text-base font-medium text-primary underline underline-offset-4">
          {t.portal.registerLink}
        </a>
      </p>
    </div>
    </main>
  )
}
