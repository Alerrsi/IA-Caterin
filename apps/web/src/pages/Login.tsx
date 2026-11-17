import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useAuth } from '../auth'
import { Dialog } from '../components/Dialog'
import { AuthLayout } from '../components/Logo'
import { Icon, type IconName } from '../components/Icon'
import { Alert, Button, Field, IconDot, inputClass } from '../components/ui'
import { DEMO_PASSWORD, DEMO_USERS, demoLoginEnabled, type DemoUserKey } from '../demoLogin'
import { t } from '../i18n'

const DEMO_ICONS: Record<DemoUserKey, IconName> = { owner: 'store', kitchen: 'restaurant', sales: 'orders', customer: 'cloche' }

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)

  async function enter(asEmail: string, asPassword: string) {
    setBusy(true)
    setError(null)
    try {
      await login(asEmail, asPassword)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    void enter(email, password)
  }

  /** Acceso rápido de demostración: entra directo con la cuenta ficticia elegida (ver `demoLogin.ts`). */
  function enterAsDemo(demoEmail: string) {
    setDemoOpen(false)
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    void enter(demoEmail, DEMO_PASSWORD)
  }

  return (
    <AuthLayout
      titleAsHeading
      headerAction={
        demoLoginEnabled && (
          <button
            type="button"
            onClick={() => setDemoOpen(true)}
            aria-haspopup="dialog"
            className="inline-flex min-h-11 items-center gap-2 rounded-full bg-accent px-4 text-sm font-bold text-on-accent shadow-cap transition-colors hover:bg-accent/85 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
          >
            {t.login.demoOpen}
          </button>
        )
      }
    >
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
      {demoOpen && (
        <Dialog label={t.login.demoTitle} onClose={() => setDemoOpen(false)}>
          <div className="flex items-start justify-between gap-2 px-5 pb-1 pt-4">
            <div>
              <h2 className="text-xl font-extrabold text-on-surface">{t.login.demoTitle}</h2>
              <p className="mt-1 text-sm text-on-surface-variant">{t.login.demoHint}</p>
            </div>
            <button
              type="button"
              onClick={() => setDemoOpen(false)}
              aria-label={t.login.demoClose}
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full hover:bg-surface-container focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
            >
              <Icon name="close" className="h-5 w-5" />
            </button>
          </div>
          <ul className="grid gap-2 overflow-y-auto px-5 pb-2 pt-2">
            {DEMO_USERS.map((u) => (
              <li key={u.key}>
                <button
                  type="button"
                  onClick={() => enterAsDemo(u.email)}
                  disabled={busy}
                  className="flex min-h-14 w-full items-center gap-3 rounded-2xl bg-surface-container p-2 text-left transition-colors hover:bg-surface-container-high focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 disabled:opacity-60"
                >
                  <IconDot name={DEMO_ICONS[u.key]} />
                  <span className="min-w-0">
                    <span className="block font-bold leading-tight text-on-surface">{t.login.demoUsers[u.key]}</span>
                    <span className="block truncate text-sm text-on-surface-variant">{u.email}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Dialog>
      )}
    </AuthLayout>
  )
}
