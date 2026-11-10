import { useEffect, useState } from 'react'
import { api, ApiError, post, type OrderOut, type QuoteOut } from '../api'
import { MarginFix, isMarginRequired } from '../components/MarginFix'
import { Alert, Button, Field, inputClass, Page, Spinner, StatusChip } from '../components/ui'
import { formatDate, formatQty } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

const linesText = (o: OrderOut) =>
  o.lines.map((l) => `${formatQty(l.qty)} ${t.units[l.unit]} ${l.recipe_name ?? l.requested_name}`).join(' · ')

export default function Orders() {
  const [orders, setOrders] = useState<OrderOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [marginFor, setMarginFor] = useState<OrderOut | null>(null)
  const [messages, setMessages] = useState<Record<string, string>>({})

  const fail = (err: unknown) => setError(err instanceof ApiError ? err.userMessage : t.genericError)

  useEffect(() => {
    api<OrderOut[]>('/orders').then(setOrders).catch(fail)
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
      else fail(err)
    } finally {
      setBusy(null)
    }
  }

  /** La dueña acepta o rechaza lo que envió un cliente del portal (ADR-007). */
  async function decide(order: OrderOut, accept: boolean) {
    setBusy(order.id)
    setError(null)
    setNotice(null)
    try {
      const out = await post<OrderOut>(`/orders/${order.id}/${accept ? 'accept' : 'reject'}`, {
        message: messages[order.id]?.trim() || null,
      })
      setOrders((prev) => prev?.map((o) => (o.id === out.id ? out : o)) ?? null)
      setNotice(accept ? t.orders.accepted : t.orders.rejected)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  const requests = orders?.filter((o) => o.status === 'requested') ?? []
  const others = orders?.filter((o) => o.status !== 'requested') ?? []

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
      {notice && (
        <div className="mb-4">
          <Alert kind="info">{notice}</Alert>
        </div>
      )}
      {!orders ? (
        !error && <Spinner label={t.loading} />
      ) : (
        <>
          {requests.length > 0 && (
            <section aria-labelledby="requests-title" className="mb-8">
              <h2 id="requests-title" className="text-xl font-bold text-stone-900">
                {t.orders.requestsTitle} ({requests.length})
              </h2>
              <p className="mb-3 text-stone-700">{t.orders.requestsHint}</p>
              <ul className="space-y-4">
                {requests.map((o) => (
                  <li key={o.id} className="rounded-2xl border-2 border-sky-700 bg-white p-4 shadow-sm" data-testid="request">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-lg font-bold">{o.customer_name}</p>
                        <p className="text-stone-700">
                          {o.event_date ? formatDate(o.event_date) : t.orders.noDate}
                          {o.submitted_at && ` · ${t.orders.sentOn(formatDate(o.submitted_at))}`}
                        </p>
                      </div>
                      <StatusChip status={o.status}>{t.orders.status[o.status]}</StatusChip>
                    </div>
                    <p className="mt-2 text-stone-700">{linesText(o)}</p>
                    {o.notes && <p className="mt-1 text-stone-700">{t.orders.customerNotes(o.notes)}</p>}
                    <div className="mt-3 flex gap-3">
                      {o.last_quote_id && (
                        <Button variant="secondary" className="flex-1" onClick={() => navigate(`/cotizaciones/${o.last_quote_id}`)}>
                          {t.orders.viewQuote}
                        </Button>
                      )}
                      <Button variant="secondary" className="flex-1" onClick={() => quote(o)} disabled={busy !== null}>
                        {t.view.recalc}
                      </Button>
                    </div>
                    <div className="mt-3">
                      <Field label={t.orders.message}>
                        <input
                          className={inputClass}
                          value={messages[o.id] ?? ''}
                          maxLength={1000}
                          onChange={(e) => setMessages((m) => ({ ...m, [o.id]: e.target.value }))}
                        />
                      </Field>
                    </div>
                    <div className="mt-3 flex gap-3">
                      <Button className="flex-1" onClick={() => decide(o, true)} disabled={busy !== null}>
                        {t.orders.accept}
                      </Button>
                      <Button variant="secondary" className="flex-1" onClick={() => decide(o, false)} disabled={busy !== null}>
                        {t.orders.reject}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {requests.length > 0 && others.length > 0 && <h2 className="mb-3 text-xl font-bold">{t.orders.otherOrders}</h2>}
          {others.length === 0 && requests.length === 0 ? (
            <p>{t.orders.empty}</p>
          ) : (
            <ul className="space-y-4">
              {others.map((o) => (
                <li key={o.id} className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-lg font-bold">{o.customer_name}</p>
                      <p className="text-stone-700">{o.event_date ? formatDate(o.event_date) : t.orders.noDate}</p>
                      {o.from_customer && <p className="text-sm text-stone-600">{t.orders.fromCustomer}</p>}
                    </div>
                    <StatusChip status={o.status}>{t.orders.status[o.status]}</StatusChip>
                  </div>
                  <p className="mt-2 text-stone-700">{linesText(o)}</p>
                  {o.owner_message && <p className="mt-1 text-sm text-stone-600">«{o.owner_message}»</p>}
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
        </>
      )}
    </Page>
  )
}
