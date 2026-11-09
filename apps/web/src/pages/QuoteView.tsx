import { useEffect, useState } from 'react'
import { api, apiBlob, ApiError, patch, post, type QuoteOut, type ShoppingList } from '../api'
import { StarSurvey } from '../components/StarSurvey'
import { Alert, Button, Page, Spinner } from '../components/ui'
import { formatCLP, formatDate, formatQty, formatWeekdays } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

export default function QuoteView({ id }: { id: string }) {
  const [quote, setQuote] = useState<QuoteOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [shopping, setShopping] = useState<ShoppingList | null>(null)

  const fail = (err: unknown) => setError(err instanceof ApiError ? err.userMessage : t.genericError)

  useEffect(() => {
    api<QuoteOut>(`/quotes/${id}`).then(setQuote).catch(fail)
  }, [id])

  async function recalc() {
    if (!quote) return
    setBusy('recalc')
    setError(null)
    try {
      const next = await post<QuoteOut>(`/orders/${quote.order_id}/quotes`, {})
      setShopping(null)
      navigate(`/cotizaciones/${next.id}`)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function openPdf() {
    setBusy('pdf')
    setError(null)
    // Se abre la pestaña antes de esperar la red: los navegadores móviles bloquean popups tardíos.
    const win = window.open('', '_blank')
    try {
      const blob = await apiBlob(`/quotes/${id}/pdf`)
      const url = URL.createObjectURL(blob)
      if (win) win.location.href = url
      else window.location.href = url
    } catch (err) {
      win?.close()
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function setStatus(status: 'sent' | 'accepted') {
    setBusy(status)
    setError(null)
    try {
      setQuote(await patch<QuoteOut>(`/quotes/${id}`, { status }))
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function toggleShopping(open: boolean) {
    if (open && !shopping) {
      api<ShoppingList>(`/quotes/${id}/shopping-list`).then(setShopping).catch(fail)
    }
  }

  if (!quote) {
    return (
      <Page title={t.view.title} onBack={() => navigate('/pedidos')}>
        {error ? <Alert>{error}</Alert> : <Spinner label={t.loading} />}
      </Page>
    )
  }

  return (
    <Page title={`${t.view.title} · ${t.view.version(quote.version)}`} onBack={() => navigate('/pedidos')}>
      <p className="mb-2 inline-block rounded-full bg-orange-100 px-3 py-1 text-sm font-semibold text-brand-dark">
        {t.view.status[quote.status]}
      </p>

      {!quote.is_complete && (
        <div className="mb-4">
          <Alert kind="warning">
            <p className="font-bold">{t.view.incompleteTitle}</p>
            <p>{t.view.incompleteBody(quote.missing_prices.join(', '))}</p>
          </Alert>
        </div>
      )}

      <section className="rounded-2xl bg-white p-5 shadow-sm" aria-label={t.view.total}>
        <p className="text-stone-700">{t.view.total}</p>
        <p className="text-4xl font-bold text-stone-900" data-testid="quote-total">
          {formatCLP(quote.total_clp)}
        </p>
        <dl className="mt-3 grid grid-cols-2 gap-1 text-stone-800">
          <dt>{t.view.net}</dt>
          <dd className="text-right">{formatCLP(quote.net_clp)}</dd>
          <dt>{t.view.vat(formatQty(quote.vat_pct))}</dt>
          <dd className="text-right">{formatCLP(quote.vat_clp)}</dd>
        </dl>
        {quote.valid_until && <p className="mt-2 text-sm text-stone-600">{t.view.validUntil(formatDate(quote.valid_until))}</p>}
      </section>

      <h2 className="mb-2 mt-6 text-xl font-bold">{t.view.products}</h2>
      <ul className="divide-y divide-stone-200 rounded-2xl bg-white shadow-sm">
        {quote.products.map((p, i) => (
          <li key={i} className="flex items-start justify-between gap-3 p-4">
            <div>
              <p className="font-semibold">{p.recipe_name}</p>
              <p className="text-stone-700">
                {formatQty(p.qty)} {p.unit_label} · {formatCLP(p.unit_price_clp)} {t.view.unitPrice}
              </p>
            </div>
            <p className="font-semibold">{formatCLP(p.subtotal_clp)}</p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm text-stone-600">
        {t.view.ingredientsCost}: {formatCLP(quote.ingredients_cost_clp)}
      </p>

      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {quote.is_complete ? (
          <Button className="w-full" onClick={openPdf} disabled={busy !== null}>
            {busy === 'pdf' ? t.view.pdfLoading : t.view.pdf}
          </Button>
        ) : (
          <Button className="w-full" onClick={recalc} disabled={busy !== null}>
            {t.view.recalc}
          </Button>
        )}
        {quote.is_complete && quote.status === 'draft' && (
          <Button variant="secondary" className="w-full" onClick={() => setStatus('sent')} disabled={busy !== null}>
            {t.view.markSent}
          </Button>
        )}
        {quote.is_complete && quote.status !== 'accepted' && (
          <Button variant="secondary" className="w-full" onClick={() => setStatus('accepted')} disabled={busy !== null}>
            {t.view.markAccepted}
          </Button>
        )}
        {quote.is_complete && (
          <Button variant="ghost" className="w-full" onClick={recalc} disabled={busy !== null}>
            {t.view.recalc}
          </Button>
        )}
      </div>

      <details className="mt-6 rounded-2xl bg-white p-4 shadow-sm" onToggle={(e) => toggleShopping(e.currentTarget.open)}>
        <summary className="min-h-12 cursor-pointer py-2 text-xl font-bold">
          {t.view.shopping} · {formatCLP(quote.shopping_total_clp)}
        </summary>
        {!shopping ? (
          <Spinner label={t.loading} />
        ) : (
          <div className="space-y-4">
            {shopping.groups.map((g) => (
              <div key={g.supplier_id}>
                <p className="font-bold">{g.supplier_name}</p>
                {g.delivery_days && g.delivery_days.length > 0 && (
                  <p className="text-sm text-stone-600">{t.view.deliveryDays(formatWeekdays(g.delivery_days))}</p>
                )}
                <ul className="mt-1">
                  {g.items.map((it) => (
                    <li key={it.ingredient_name} className="flex justify-between gap-2 py-1">
                      <span>
                        {it.packages} × {it.package_label} — {it.ingredient_name}
                      </span>
                      <span>{formatCLP(it.total_clp)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {shopping.without_price.length > 0 && (
              <p className="text-amber-900">
                {t.view.withoutPrice}: {shopping.without_price.join(', ')}
              </p>
            )}
            {shopping.covered_by_stock.length > 0 && (
              <p className="text-stone-700">
                {t.view.coveredByStock}: {shopping.covered_by_stock.join(', ')}
              </p>
            )}
            <p className="font-bold">
              {t.view.shoppingTotal}: {formatCLP(shopping.total_clp)}
            </p>
          </div>
        )}
      </details>

      <div className="mt-6">
        <StarSurvey key={id} context="quote" />
      </div>
    </Page>
  )
}
