import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useAuth } from '../auth'
import { AuthLayout } from '../components/Logo'
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
    <AuthLayout titleAsHeading>
      <h2 className="mb-3 text-2xl font-extrabold text-on-surface lg:mb-4">{t.login.title}</h2>
      <form onSubmit={submit} className="space-y-3" noValidate>
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
      {/* Dos enlaces apilados de 44 px: táctiles y sin empujar el formulario fuera de la primera vista. */}
      <p className="mt-2 text-center">
        <a href="#/registro" className="inline-flex min-h-11 items-center text-base font-semibold text-primary underline underline-offset-4">
          {t.register.link}
        </a>
      </p>
      <p className="text-center">
        <a href="#/cliente" className="inline-flex min-h-11 items-center text-sm font-medium text-primary underline underline-offset-4">
          {t.portal.registerLink}
        </a>
      </p>
    </AuthLayout>
  )
}
