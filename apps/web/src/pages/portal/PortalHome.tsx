import { useEffect, useState } from 'react'
import { api, ApiError, type PortalRequestSummary } from '../../api'
import { useAuth } from '../../auth'
import { Alert, Button, Page, Spinner, StatusChip } from '../../components/ui'
import { formatCLP, formatDate } from '../../format'
import { t } from '../../i18n'
import { navigate } from '../../router'

/** Inicio del cliente del portal (ADR-007): sus cotizaciones guardadas y el botón para cotizar otra. */
export default function PortalHome() {
  const { user, pyme, logout } = useAuth()
  const [items, setItems] = useState<PortalRequestSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<PortalRequestSummary[]>('/portal/requests')
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [])

  return (
    <Page title={t.portal.homeTitle}>
      <p className="mb-4 text-stone-700">{t.portal.hello(user?.full_name.split(' ')[0] ?? '', pyme?.name ?? '')}</p>
      <button
        type="button"
        onClick={() => navigate('/cotizar')}
        className="mb-6 block w-full rounded-2xl border-2 border-brand bg-white p-5 text-left text-brand shadow-sm hover:bg-orange-50 focus-visible:ring-4 focus-visible:ring-orange-300"
      >
        <span className="block text-xl font-semibold">{t.portal.newQuote}</span>
        <span className="mt-1 block">{t.portal.newQuoteHint}</span>
      </button>
      {error && <Alert>{error}</Alert>}
      {!items ? (
        !error && <Spinner label={t.loading} />
      ) : items.length === 0 ? (
        <p className="text-stone-700">{t.portal.empty}</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => navigate(`/solicitudes/${r.id}`)}
                className="block h-full w-full rounded-2xl bg-white p-4 text-left shadow-sm hover:bg-orange-50 focus-visible:ring-4 focus-visible:ring-orange-300"
              >
                <div className="flex items-start justify-between gap-2">
                  <StatusChip status={r.status}>{t.portal.status[r.status]}</StatusChip>
                  <span className="text-lg font-semibold">{r.total_clp === null ? t.portal.noTotal : formatCLP(r.total_clp)}</span>
                </div>
                <p className="mt-2 text-stone-900">{r.products}</p>
                <p className="mt-1 text-sm text-stone-700">
                  {r.event_date ? t.portal.eventDate(formatDate(r.event_date)) : t.orders.noDate}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Button variant="ghost" className="mt-8" onClick={() => void logout()}>
        {t.home.logout}
      </Button>
    </Page>
  )
}
