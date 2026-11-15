import { useEffect, useState } from 'react'
import { api, ApiError, type PortalRequestSummary } from '../../api'
import { useAuth } from '../../auth'
import { Icon } from '../../components/Icon'
import { Alert, Page, Spinner, StatusChip } from '../../components/ui'
import { formatCLP, formatDate } from '../../format'
import { t } from '../../i18n'
import { navigate } from '../../router'

/** Inicio del cliente del portal (ADR-007): sus cotizaciones guardadas y el botón para cotizar otra. */
export default function PortalHome() {
  const { user } = useAuth()
  const [items, setItems] = useState<PortalRequestSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<PortalRequestSummary[]>('/portal/requests')
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [])

  return (
    <Page title={t.portal.homeTitle}>
      <p className="mb-4 text-on-surface-variant">{t.portal.hello(user?.full_name.split(' ')[0] ?? '')}</p>
      <button
        type="button"
        onClick={() => navigate('/cotizar')}
        className="mb-6 block w-full rounded-xl bg-primary-container p-5 text-left text-on-primary-container transition hover:shadow-md focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30"
      >
        <span className="block text-lg font-medium">{t.portal.newQuote}</span>
        <span className="mt-1 block">{t.portal.newQuoteHint}</span>
      </button>
      <a
        href="#/pymes"
        className="-mt-3 mb-6 flex items-center gap-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4 text-on-surface transition hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30"
      >
        <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-tertiary-container text-on-tertiary-container">
          <Icon name="store" />
        </span>
        <span>
          <span className="block text-lg font-medium">{t.catalog.homeLink}</span>
          <span className="block text-on-surface-variant">{t.catalog.homeLinkHint}</span>
        </span>
      </a>
      {error && <Alert>{error}</Alert>}
      {!items ? (
        !error && <Spinner label={t.loading} />
      ) : items.length === 0 ? (
        <p className="text-on-surface-variant">{t.portal.empty}</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => navigate(`/solicitudes/${r.id}`)}
                className="block h-full w-full rounded-xl bg-surface-container-lowest p-4 text-left border border-outline-variant hover:bg-surface-container focus-visible:ring-4 focus-visible:ring-primary/40"
              >
                <div className="flex items-start justify-between gap-2">
                  <StatusChip status={r.status}>{t.portal.status[r.status]}</StatusChip>
                  <span className="text-lg font-medium">{r.total_clp === null ? t.portal.noTotal : formatCLP(r.total_clp)}</span>
                </div>
                <p className="mt-2 text-sm font-medium text-on-surface-variant">{r.pyme_name}</p>
                <p className="mt-1 text-on-surface">{r.products}</p>
                <p className="mt-1 text-sm text-on-surface-variant">
                  {r.event_date ? t.portal.eventDate(formatDate(r.event_date)) : t.orders.noDate}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
