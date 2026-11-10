import { useState } from 'react'
import { loadAllIngredients, type Ingredient, type Movement } from '../api'
import { PriceSection } from '../components/PriceForm'
import { StockAdjust, applyDelta } from '../components/StockAdjust'
import { Alert, Button, Page, Spinner } from '../components/ui'
import { formatStock } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { savedAtLabel, usePendingIngredients, useReloadWhenSynced } from './Inventory'

export default function IngredientDetail({ id }: { id: string }) {
  const list = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const history = useCached<{ items: Movement[] }>(`movements:${id}`, `/ingredients/${id}/movements?limit=20`)
  const [sign, setSign] = useState<1 | -1 | null>(null)
  const [notice, setNotice] = useState<{ kind: 'info' | 'warning'; text: string } | null>(null)
  const pendingIds = usePendingIngredients()
  useReloadWhenSynced(list.reload)
  useReloadWhenSynced(history.reload)

  const ing = list.value?.data.find((i) => i.id === id)

  function applied(deltaBase: number) {
    if (!ing) return
    list.setData((all) => all.map((i) => (i.id === id ? applyDelta(i, deltaBase) : i)))
    setSign(null)
    if (Number(applyDelta(ing, deltaBase).stock_qty) < 0) setNotice({ kind: 'warning', text: t.inventory.wentNegative })
    else if (!navigator.onLine) setNotice({ kind: 'info', text: t.sync.savedLocally })
    else setNotice(null)
  }

  return (
    <Page title={ing?.name ?? t.inventory.title} onBack={() => navigate('/inventario')}>
      {list.value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(list.value.savedAt))}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-3">
          <Alert kind={notice.kind}>{notice.text}</Alert>
        </div>
      )}
      {!ing ? (
        list.error ? (
          <Alert>{list.error.code === 'offline_no_cache' ? t.sync.noCache : list.error.userMessage}</Alert>
        ) : list.loading ? (
          <Spinner label={t.loading} />
        ) : (
          <Alert>{t.inventory.empty}</Alert>
        )
      ) : (
        <>
          <section className="rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
            <p className="text-on-surface-variant">{t.inventory.stock}</p>
            <p className="text-3xl font-medium text-on-surface">{formatStock(ing.stock_qty, ing.base_unit)}</p>
            {ing.min_stock_qty && (
              <p className={ing.is_low ? 'font-medium text-on-warning-container' : 'text-on-surface-variant'}>
                {ing.is_low && `${t.inventory.low} · `}
                {t.inventory.min(formatStock(ing.min_stock_qty, ing.base_unit))}
              </p>
            )}
            {ing.category && (
              <p className="text-on-surface-variant">
                {t.inventory.category}: {ing.category}
              </p>
            )}
            {pendingIds.has(ing.id) && (
              <span className="mt-1 inline-block rounded-full bg-surface-container-highest px-2 py-0.5 text-sm font-medium text-on-surface">
                {t.inventory.pendingBadge}
              </span>
            )}
            <h2 className="mt-4 font-medium text-on-surface">{t.inventory.adjust}</h2>
            <div className="mt-2 flex gap-2">
              <Button variant="secondary" className="flex-1 text-2xl" aria-label={t.inventory.remove(ing.name)} onClick={() => setSign(-1)}>
                −
              </Button>
              <Button className="flex-1 text-2xl" aria-label={t.inventory.add(ing.name)} onClick={() => setSign(1)}>
                +
              </Button>
            </div>
            {sign !== null && (
              <StockAdjust key={sign} ingredient={ing} sign={sign} onDone={applied} onCancel={() => setSign(null)} />
            )}
          </section>

          <PriceSection ingredient={ing} />

          <section className="mt-4 rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
            <h2 className="mb-2 text-lg font-medium text-on-surface">{t.inventory.history}</h2>
            {history.value ? (
              history.value.data.items.length === 0 ? (
                <p>{t.inventory.noHistory}</p>
              ) : (
                <ul className="divide-y divide-outline-variant">
                  {history.value.data.items.map((m) => (
                    <li key={m.id} className="flex justify-between gap-3 py-2">
                      <span>
                        <span className="block font-medium">{t.inventory.reasons[m.reason] ?? m.reason}</span>
                        <span className="block text-sm text-on-surface-variant">
                          {savedAtLabel(m.occurred_at)}
                          {m.note ? ` · ${m.note}` : ''}
                        </span>
                      </span>
                      <span className={`shrink-0 font-medium ${Number(m.delta_qty) < 0 ? 'text-on-error-container' : 'text-on-success-container'}`}>
                        {Number(m.delta_qty) > 0 ? '+' : ''}
                        {formatStock(m.delta_qty, ing.base_unit)}
                      </span>
                    </li>
                  ))}
                </ul>
              )
            ) : history.error ? (
              <p className="text-on-surface-variant">{history.error.status === 0 ? t.inventory.historyOffline : history.error.userMessage}</p>
            ) : (
              <Spinner label={t.loading} />
            )}
          </section>
        </>
      )}
    </Page>
  )
}
