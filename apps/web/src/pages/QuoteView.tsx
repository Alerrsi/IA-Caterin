import { useEffect, useState } from 'react'
import { api, apiBlob, ApiError, loadAllIngredients, patch, post, type Ingredient, type QuoteOut, type ShoppingList } from '../api'
import { MarginFix, isMarginRequired } from '../components/MarginFix'
import { StarSurvey } from '../components/StarSurvey'
import { Alert, Button, Page, Spinner, StatusChip } from '../components/ui'
import { formatCLP, formatDate, formatQty, formatWeekdays } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { plain } from './Inventory'

export default function QuoteView({ id }: { id: string }) {
  const [quote, setQuote] = useState<QuoteOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [shopping, setShopping] = useState<ShoppingList | null>(null)
  const [needsMargin, setNeedsMargin] = useState(false)
  // La API da los nombres de los insumos sin precio: se resuelven contra el inventario guardado para enlazarlos.
  const ingredients = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const idByName = new Map((ingredients.value?.data ?? []).map((i) => [plain(i.name), i.id]))

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
      setNeedsMargin(false)
      navigate(`/cotizaciones/${next.id}`)
    } catch (err) {
      if (isMarginRequired(err)) setNeedsMargin(true)
      else fail(err)
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
      <div className="mb-4">
        <StatusChip status={quote.status}>{t.view.status[quote.status]}</StatusChip>
      </div>

      {!quote.is_complete && (
        <div className="mb-4">
          <Alert kind="warning">
            <p className="font-medium">{t.view.incompleteTitle}</p>
            <p>{t.view.incompleteBody(quote.missing_prices.join(', '))}</p>
            {quote.missing_prices.some((n) => idByName.has(plain(n))) && (
              <>
                <p className="mt-2 font-medium">{t.view.missingLinksTitle}</p>
                <ul className="mt-1 flex flex-wrap gap-2">
                  {quote.missing_prices.map((name) => {
                    const ingId = idByName.get(plain(name))
                    return ingId ? (
                      <li key={name}>
                        <Button
                          variant="secondary"
                          aria-label={t.view.addPriceFor(name)}
                          onClick={() => navigate(`/inventario/${ingId}`)}
                        >
                          {name}
                        </Button>
                      </li>
                    ) : (
                      <li key={name} className="self-center">
                        {name}
                      </li>
                    )
                  })}
                </ul>
              </>
            )}
          </Alert>
        </div>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <aside className="space-y-4 lg:sticky lg:top-6 lg:col-start-2 lg:row-start-1">
      <section className="rounded-xl bg-surface-container-lowest p-5 border border-outline-variant" aria-label={t.view.total}>
        <p className="text-on-surface-variant">{t.view.total}</p>
        <p className="text-4xl font-normal text-on-surface" data-testid="quote-total">
          {formatCLP(quote.total_clp)}
        </p>
        <dl className="mt-3 grid grid-cols-2 gap-1 text-on-surface">
          <dt>{t.view.net}</dt>
          <dd className="text-right">{formatCLP(quote.net_clp)}</dd>
          <dt>{t.view.vat(formatQty(quote.vat_pct))}</dt>
          <dd className="text-right">{formatCLP(quote.vat_clp)}</dd>
        </dl>
        {quote.valid_until && <p className="mt-2 text-sm text-on-surface-variant">{t.view.validUntil(formatDate(quote.valid_until))}</p>}
      </section>

      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {needsMargin && (
        <div className="mt-4">
          <MarginFix onSaved={recalc} />
        </div>
      )}

      <div className="space-y-3">
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

        </aside>
        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
      <h2 className="mb-2 text-lg font-medium">{t.view.products}</h2>
      <ul className="divide-y divide-outline-variant rounded-xl bg-surface-container-lowest border border-outline-variant">
        {quote.products.map((p, i) => (
          <li key={i} className="flex items-start justify-between gap-3 p-4">
            <div>
              <p className="font-medium">{p.recipe_name}</p>
              <p className="text-on-surface-variant">
                {formatQty(p.qty)} {p.unit_label} · {formatCLP(p.unit_price_clp)} {t.view.unitPrice}
              </p>
            </div>
            <p className="font-medium">{formatCLP(p.subtotal_clp)}</p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm text-on-surface-variant">
        {t.view.ingredientsCost}: {formatCLP(quote.ingredients_cost_clp)}
      </p>

      <details className="mt-6 rounded-xl bg-surface-container-lowest p-4 border border-outline-variant" onToggle={(e) => toggleShopping(e.currentTarget.open)}>
        <summary className="min-h-12 cursor-pointer py-2 text-xl font-medium">
          {t.view.shopping} · {formatCLP(quote.shopping_total_clp)}
        </summary>
        {!shopping ? (
          <Spinner label={t.loading} />
        ) : (
          <div className="space-y-4">
            {shopping.groups.map((g) => (
              <div key={g.supplier_id}>
                <p className="font-medium">{g.supplier_name}</p>
                {g.delivery_days && g.delivery_days.length > 0 && (
                  <p className="text-sm text-on-surface-variant">{t.view.deliveryDays(formatWeekdays(g.delivery_days))}</p>
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
              <p className="text-on-warning-container">
                {t.view.withoutPrice}: {shopping.without_price.join(', ')}
              </p>
            )}
            {shopping.covered_by_stock.length > 0 && (
              <p className="text-on-surface-variant">
                {t.view.coveredByStock}: {shopping.covered_by_stock.join(', ')}
              </p>
            )}
            <p className="font-medium">
              {t.view.shoppingTotal}: {formatCLP(shopping.total_clp)}
            </p>
          </div>
        )}
      </details>

      <div className="mt-6">
        <StarSurvey key={id} context="quote" />
      </div>
        </div>
      </div>
    </Page>
  )
}
