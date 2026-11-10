import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api, customerLink, patch, post, type PymeSettings, type User } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, Page, Spinner, inputClass, useOnline } from '../components/ui'
import { t } from '../i18n'
import { navigate } from '../router'

/** "19,5" -> "19.5". Porcentaje entre 0 y 100, con hasta 2 decimales; null si no es válido. */
function parsePct(raw: string): string | null {
  const cleaned = raw.trim().replace(/\s/g, '').replace(',', '.')
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(cleaned)) return null
  return Number(cleaned) <= 100 ? cleaned : null
}

function pctText(value: string | null): string {
  return value === null ? '' : String(Number(value)).replace('.', ',')
}

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.userMessage : t.genericError
}

function PymeForm({ online }: { online: boolean }) {
  const [pyme, setPyme] = useState<PymeSettings | null>(null)
  const [form, setForm] = useState({ name: '', margin: '', waste: '', vat: '', validity: '', includesVat: true })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<PymeSettings>('/pyme')
      .then((p) => {
        setPyme(p)
        setForm({
          name: p.name,
          margin: pctText(p.default_margin_pct),
          waste: pctText(p.default_waste_pct),
          vat: pctText(p.vat_pct),
          validity: p.quote_validity_days === null ? '' : String(p.quote_validity_days),
          includesVat: p.prices_include_vat,
        })
      })
      .catch((err) => setError(errorText(err)))
  }, [])

  const set = (field: keyof typeof form) => (value: string | boolean) => {
    setSaved(false)
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    const margin = form.margin.trim() === '' ? null : parsePct(form.margin)
    const waste = parsePct(form.waste)
    const vat = parsePct(form.vat)
    const validity = form.validity.trim() === '' ? null : Number(form.validity)
    if ((form.margin.trim() !== '' && margin === null) || waste === null || vat === null) {
      setError(t.settings.badNumber)
      return
    }
    if (validity !== null && (!Number.isInteger(validity) || validity < 1 || validity > 365)) {
      setError(t.settings.badNumber)
      return
    }
    setBusy(true)
    try {
      const out = await patch<PymeSettings>('/pyme', {
        name: form.name.trim(),
        default_margin_pct: margin,
        default_waste_pct: waste,
        vat_pct: vat,
        quote_validity_days: validity,
        prices_include_vat: form.includesVat,
      })
      setPyme(out)
      setSaved(true)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!pyme) return error ? <Alert>{error}</Alert> : <Spinner label={t.loading} />
  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-4 shadow-sm" noValidate>
      <h2 className="text-xl font-bold text-stone-900">{t.settings.pyme}</h2>
      <Field label={t.settings.name}>
        <input className={inputClass} value={form.name} onChange={(e) => set('name')(e.target.value)} maxLength={120} />
      </Field>
      <Field label={t.settings.margin} hint={t.settings.marginHint}>
        <input className={inputClass} inputMode="decimal" value={form.margin} onChange={(e) => set('margin')(e.target.value)} />
      </Field>
      <Field label={t.settings.waste} hint={t.settings.wasteHint}>
        <input className={inputClass} inputMode="decimal" value={form.waste} onChange={(e) => set('waste')(e.target.value)} />
      </Field>
      <Field label={t.settings.vat}>
        <input className={inputClass} inputMode="decimal" value={form.vat} onChange={(e) => set('vat')(e.target.value)} />
      </Field>
      <Field label={t.settings.validity}>
        <input className={inputClass} inputMode="numeric" value={form.validity} onChange={(e) => set('validity')(e.target.value)} />
      </Field>
      <label className="flex min-h-12 items-center gap-3 text-lg">
        <input
          type="checkbox"
          className="h-6 w-6 accent-orange-800"
          checked={form.includesVat}
          onChange={(e) => set('includesVat')(e.target.checked)}
        />
        {t.settings.pricesIncludeVat}
      </label>
      {error && <Alert>{error}</Alert>}
      {saved && <Alert kind="info">{t.settings.saved}</Alert>}
      {!online && <p className="text-stone-700">{t.sync.needsNetwork}</p>}
      <Button type="submit" className="w-full" disabled={busy || !online}>
        {busy ? t.loading : t.settings.save}
      </Button>
    </form>
  )
}

function Team({ online }: { online: boolean }) {
  const [users, setUsers] = useState<User[] | null>(null)
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<User[]>('/users')
      .then(setUsers)
      .catch((err) => setError(errorText(err)))
  }, [])

  async function invite(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setDone(null)
    setBusy(true)
    try {
      const user = await post<User>('/users', {
        email: form.email.trim(),
        full_name: form.name.trim(),
        password: form.password,
        role: 'collaborator',
      })
      setUsers((all) => [...(all ?? []), user])
      setForm({ name: '', email: '', password: '' })
      setDone(t.settings.invited(user.full_name))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const ready = form.name.trim().length >= 2 && form.email.includes('@') && form.password.length >= 10
  return (
    <section className="space-y-4 rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="text-xl font-bold text-stone-900">{t.settings.team}</h2>
      {users === null ? (
        !error && <Spinner label={t.loading} />
      ) : (
        <ul className="divide-y divide-stone-200">
          {users.map((u) => (
            <li key={u.id} className="py-2">
              <p className="font-semibold text-stone-900">{u.full_name}</p>
              <p className="break-all text-stone-700">{u.email}</p>
              <p className="text-sm text-stone-700">
                {t.settings.roles[u.role]}
                {!u.is_active && ` · ${t.settings.inactive}`}
              </p>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={invite} className="space-y-3 border-t border-stone-200 pt-4" noValidate>
        <h3 className="text-lg font-bold text-stone-900">{t.settings.invite}</h3>
        <Field label={t.settings.inviteName}>
          <input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label={t.settings.inviteEmail}>
          <input
            className={inputClass}
            type="email"
            inputMode="email"
            autoComplete="off"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label={t.settings.invitePassword} hint={t.settings.inviteHint}>
          <input
            className={inputClass}
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        {done && <Alert kind="info">{done}</Alert>}
        <Button type="submit" className="w-full" disabled={busy || !online || !ready}>
          {busy ? t.loading : t.settings.inviteSend}
        </Button>
      </form>
    </section>
  )
}

/** Enlace del portal de clientes (ADR-007): crearlo, copiarlo, cambiarlo o cerrar el registro. */
function CustomerPortal({ online }: { online: boolean }) {
  const [code, setCode] = useState<string | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<PymeSettings>('/pyme')
      .then((p) => setCode(p.customer_code ?? null))
      .catch((err) => setError(errorText(err)))
  }, [])

  async function change(method: 'POST' | 'DELETE') {
    setBusy(true)
    setError(null)
    setCopied(false)
    try {
      const p = await api<PymeSettings>('/pyme/customer-code', { method })
      setCode(p.customer_code ?? null)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function copy(link: string) {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const link = code ? customerLink(code) : null
  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="text-xl font-bold text-stone-900">{t.settings.customersTitle}</h2>
      <p className="text-stone-700">{t.settings.customersHint}</p>
      {code === undefined && !error && <Spinner label={t.loading} />}
      {link ? (
        <>
          <p className="break-all rounded-xl bg-stone-100 p-3 font-mono text-base" data-testid="customer-link">
            {link}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button className="flex-1" onClick={() => copy(link)}>
              {t.settings.copy}
            </Button>
            <Button variant="secondary" className="flex-1" onClick={() => change('POST')} disabled={busy || !online}>
              {t.settings.customersNew}
            </Button>
          </div>
          <Button variant="ghost" onClick={() => change('DELETE')} disabled={busy || !online}>
            {t.settings.customersClose}
          </Button>
        </>
      ) : (
        code === null && (
          <>
            <p className="text-stone-700">{t.settings.customersOff}</p>
            <Button className="w-full" onClick={() => change('POST')} disabled={busy || !online}>
              {t.settings.customersOpen}
            </Button>
          </>
        )
      )}
      {copied && <Alert kind="info">{t.settings.copied}</Alert>}
      {error && <Alert>{error}</Alert>}
    </section>
  )
}

export default function Settings() {
  const { user } = useAuth()
  const online = useOnline()
  return (
    <Page title={t.settings.title} onBack={() => navigate('/')}>
      {user?.role !== 'owner' ? (
        <Alert kind="info">{t.settings.ownerOnly}</Alert>
      ) : (
        <div className="space-y-6">
          <PymeForm online={online} />
          <CustomerPortal online={online} />
          <Team online={online} />
        </div>
      )}
    </Page>
  )
}
