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
    <main className="mx-auto w-full max-w-md px-4 pt-10">
      <h1 className="text-4xl font-bold text-brand">{t.appName}</h1>
      <p className="mb-8 mt-1 text-stone-700">{t.tagline}</p>
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
        <a href="#/registro" className="inline-block min-h-12 py-3 text-lg font-semibold text-brand underline underline-offset-4">
          {t.register.link}
        </a>
      </p>
    </main>
  )
}
