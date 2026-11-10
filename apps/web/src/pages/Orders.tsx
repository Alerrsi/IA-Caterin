import { useEffect, useState } from 'react'
import { api, ApiError, post, type OrderOut, type QuoteOut } from '../api'
import { MarginFix, isMarginRequired } from '../components/MarginFix'
import { Alert, Button, Page, Spinner } from '../components/ui'
import { formatDate, formatQty } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

export default function Orders() {
  const [orders, setOrders] = useState<OrderOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [marginFor, setMarginFor] = useState<OrderOut | null>(null)

  useEffect(() => {
    api<OrderOut[]>('/orders')
      .then(setOrders)
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [])

  async function quote(order: OrderOut) {
    setBusy(order.id)
    setError(null)
    setMarginFor(null)
    try {
      const q = await post<QuoteOut>(`/orders/${order.id}/quotes`, {})
      navigate(`/cotizaciones/${q.id}`)
    } catch (err) {
      if (isMarginRequired(err)) setMarginFor(order)
      else if (err instanceof ApiError && err.status === 403) setError(t.quote.ownerOnly.split('.')[0] + '.')
      else setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Page title={t.orders.title} onBack={() => navigate('/')}>
      {marginFor && (
        <div className="mb-4">
          <MarginFix onSaved={() => quote(marginFor)} />
        </div>
      )}
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!orders ? (
        !error && <Spinner label={t.loading} />
      ) : orders.length === 0 ? (
        <p>{t.orders.empty}</p>
      ) : (
        <ul className="space-y-4">
          {orders.map((o) => (
            <li key={o.id} className="rounded-2xl bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-lg font-bold">{o.customer_name}</p>
                  <p className="text-stone-700">{o.event_date ? formatDate(o.event_date) : t.orders.noDate}</p>
                </div>
                <span className="rounded-full bg-stone-100 px-3 py-1 text-sm font-semibold text-stone-800">
                  {t.orders.status[o.status]}
                </span>
              </div>
              <p className="mt-2 text-stone-700">
                {o.lines.map((l) => `${formatQty(l.qty)} ${t.units[l.unit]} ${l.recipe_name ?? l.requested_name}`).join(' · ')}
              </p>
              <div className="mt-3 flex gap-3">
                {o.last_quote_id && (
                  <Button variant="secondary" className="flex-1" onClick={() => navigate(`/cotizaciones/${o.last_quote_id}`)}>
                    {t.orders.viewQuote}
                  </Button>
                )}
                {o.status !== 'cancelled' && (
                  <Button className="flex-1" onClick={() => quote(o)} disabled={busy !== null}>
                    {busy === o.id ? t.quote.calculating : t.orders.quote}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
