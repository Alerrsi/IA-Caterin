import { useEffect, useMemo, useRef, useState } from 'react'
import { loadAllIngredients, type Ingredient } from '../api'
import { StockAdjust, applyDelta } from '../components/StockAdjust'
import { Alert, Button, Page, Spinner, inputClass } from '../components/ui'
import { formatStock } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { useQueue } from '../offline/queue'
import { navigate } from '../router'

export function plain(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

/** "2026-11-09T14:32:00Z" -> "09-11-2026 11:32" en la hora local del teléfono. */
export function savedAtLabel(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Ids de insumos con movimientos todavía en la cola. */
export function usePendingIngredients(): Set<string> {
  const { pending } = useQueue()
  return useMemo(
    () =>
      new Set(
        pending
          .filter((op) => op.path === '/stock/movements')
          .map((op) => (op.body as { ingredient_id?: string }).ingredient_id ?? ''),
      ),
    [pending],
  )
}

/** Cuando la cola termina de enviar, vuelve a pedir el dato real al servidor. */
export function useReloadWhenSynced(reload: () => void): void {
  const { pending } = useQueue()
  const prev = useRef(pending.length)
  useEffect(() => {
    const before = prev.current
    prev.current = pending.length
    if (before > 0 && pending.length === 0) {
      const timer = window.setTimeout(reload, 0)
      return () => window.clearTimeout(timer)
    }
  }, [pending.length, reload])
}

export default function Inventory() {
  const { value, error, loading, setData, reload } = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const [query, setQuery] = useState('')
  const [onlyLow, setOnlyLow] = useState(false)
  const [onlyNoPrice, setOnlyNoPrice] = useState(false)
  // Precios vigentes de todos los insumos en una llamada: con eso se sabe cuáles no tienen precio.
  const prices = useCached<{ ingredient_id: string }[]>('prices:current', '/prices')
  const priced = useMemo(
    () => (prices.value ? new Set(prices.value.data.map((p) => p.ingredient_id)) : null),
    [prices.value],
  )
  const [open, setOpen] = useState<{ id: string; sign: 1 | -1 } | null>(null)
  const [notice, setNotice] = useState<{ kind: 'info' | 'warning'; text: string } | null>(null)
  const pendingIds = usePendingIngredients()
  useReloadWhenSynced(reload)

  const items = useMemo(() => {
    const q = plain(query)
    return (value?.data ?? [])
      .filter((i) => i.is_active && (!onlyLow || i.is_low) && (!q || plain(i.name).includes(q)))
      .filter((i) => !onlyNoPrice || !priced || !priced.has(i.id))
      .sort((a, b) => a.name.localeCompare(b.name, 'es'))
  }, [value, query, onlyLow, onlyNoPrice, priced])

  function applied(ing: Ingredient, deltaBase: number) {
    const updated = applyDelta(ing, deltaBase)
    setData((all) => all.map((i) => (i.id === ing.id ? applyDelta(i, deltaBase) : i)))
    setOpen(null)
    if (Number(updated.stock_qty) < 0) setNotice({ kind: 'warning', text: t.inventory.wentNegative })
    else if (!navigator.onLine) setNotice({ kind: 'info', text: t.sync.savedLocally })
    else setNotice(null)
  }

  return (
    <Page title={t.inventory.title} onBack={() => navigate('/')}>
      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-3">
          <Alert kind={notice.kind}>{notice.text}</Alert>
        </div>
      )}
      <Button className="mb-4 w-full" onClick={() => navigate('/inventario/nuevo')}>
        {t.inventory.newItem}
      </Button>
      <label htmlFor="inventory-search" className="mb-1 block font-medium text-on-surface">
        {t.inventory.search}
      </label>
      <input
        id="inventory-search"
        type="search"
        className={inputClass}
        placeholder={t.inventory.searchPlaceholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoComplete="off"
      />
      <label className="mt-3 flex min-h-12 items-center gap-3 text-lg">
        <input
          type="checkbox"
          className="h-6 w-6 accent-primary"
          checked={onlyLow}
          onChange={(e) => setOnlyLow(e.target.checked)}
        />
        {t.inventory.onlyLow}
      </label>
      {priced && (
        <label className="flex min-h-12 items-center gap-3 text-lg">
          <input
            type="checkbox"
            className="h-6 w-6 accent-primary"
            checked={onlyNoPrice}
            onChange={(e) => setOnlyNoPrice(e.target.checked)}
          />
          {t.inventory.onlyNoPrice}
        </label>
      )}

      {error && !value ? (
        <div className="mt-4">
          <Alert>{error.code === 'offline_no_cache' ? t.sync.noCache : error.userMessage}</Alert>
        </div>
      ) : !value ? (
        loading && <Spinner label={t.loading} />
      ) : value.data.length === 0 ? (
        <p className="mt-4">{t.inventory.noItems}</p>
      ) : items.length === 0 ? (
        <p className="mt-4">{t.inventory.empty}</p>
      ) : (
        <ul className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((ing) => (
            <li key={ing.id} className="rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => navigate(`/inventario/${ing.id}`)}
                  className="min-h-12 min-w-0 flex-1 rounded-xl text-left focus-visible:ring-4 focus-visible:ring-primary/40"
                >
                  <span className="block text-lg font-medium text-on-surface">{ing.name}</span>
                  <span className="block text-on-surface">{formatStock(ing.stock_qty, ing.base_unit)}</span>
                  {ing.is_low && (
                    <span className="mt-1 inline-block rounded-full bg-warning-container px-2 py-0.5 text-sm font-medium text-on-warning-container">
                      {t.inventory.low}
                      {ing.min_stock_qty && ` · ${t.inventory.min(formatStock(ing.min_stock_qty, ing.base_unit))}`}
                    </span>
                  )}
                  {priced && !priced.has(ing.id) && (
                    <span className="mt-1 ml-1 inline-block rounded-full bg-error-container px-2 py-0.5 text-sm font-medium text-on-error-container">
                      {t.inventory.noPrice}
                    </span>
                  )}
                  {pendingIds.has(ing.id) && (
                    <span className="mt-1 ml-1 inline-block rounded-full bg-surface-container-highest px-2 py-0.5 text-sm font-medium text-on-surface">
                      {t.inventory.pendingBadge}
                    </span>
                  )}
                </button>
                <Button
                  variant="secondary"
                  className="w-12 shrink-0 px-0 text-2xl"
                  aria-label={t.inventory.remove(ing.name)}
                  onClick={() => setOpen({ id: ing.id, sign: -1 })}
                >
                  −
                </Button>
                <Button
                  className="w-12 shrink-0 px-0 text-2xl"
                  aria-label={t.inventory.add(ing.name)}
                  onClick={() => setOpen({ id: ing.id, sign: 1 })}
                >
                  +
                </Button>
              </div>
              {open?.id === ing.id && (
                <StockAdjust
                  key={`${ing.id}${open.sign}`}
                  ingredient={ing}
                  sign={open.sign}
                  onDone={(delta) => applied(ing, delta)}
                  onCancel={() => setOpen(null)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
