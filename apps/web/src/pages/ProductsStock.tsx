import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError, api, post, type ProductMovement, type ProductStock, type Production } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { Alert, Button, Field, Num, Page, Spinner, inputClass, useOnline } from '../components/ui'
import { formatDate, formatQty, formatStock, parseQtyInput } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { enqueue } from '../offline/queue'
import { navigate } from '../router'
import { InventoryTabs, savedAtLabel, useReloadWhenSynced } from './Inventory'

const p = t.products

/** Cifra con signo para el historial: "+48", "−6". */
function signed(qty: string, unit: ProductStock['yield_unit']): string {
  const n = Number(qty)
  return `${n > 0 ? '+' : '−'}${formatStock(String(Math.abs(n)), unit)}`
}

function AdjustForm({
  product,
  onDone,
  onCancel,
}: {
  product: ProductStock
  onDone: (delta: number) => void
  onCancel: () => void
}) {
  const [reason, setReason] = useState<'adjustment' | 'waste'>('adjustment')
  const [sign, setSign] = useState<1 | -1>(-1)
  const [qty, setQty] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const value = parseQtyInput(qty)
    if (value === null) return setError(p.badQty)
    const delta = (reason === 'waste' ? -1 : sign) * Number(value)
    await enqueue({
      path: '/products/movements',
      body: { recipe_id: product.recipe_id, reason, delta_qty: String(delta), note: note.trim() || null },
      label: `${p.title} · ${product.name}: ${delta > 0 ? '+' : ''}${formatQty(String(delta))}`,
    })
    onDone(delta)
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 border-t border-hairline pt-3" noValidate>
      <Field label={p.reason}>
        <select className={inputClass} value={reason} onChange={(e) => setReason(e.target.value as typeof reason)}>
          <option value="adjustment">{p.reasons.adjustment}</option>
          <option value="waste">{p.reasons.waste}</option>
        </select>
      </Field>
      {reason === 'adjustment' && (
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-on-surface-variant">{p.direction}</legend>
          <div className="flex gap-2">
            {([-1, 1] as const).map((s) => (
              <Button
                key={s}
                variant={sign === s ? 'tonal' : 'secondary'}
                aria-pressed={sign === s}
                className="flex-1"
                onClick={() => setSign(s)}
              >
                {s === 1 ? p.add : p.remove}
              </Button>
            ))}
          </div>
        </fieldset>
      )}
      <Field label={p.qty}>
        <input className={inputClass} inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} />
      </Field>
      <Field label={p.note}>
        <input className={inputClass} value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {error && <Alert>{error}</Alert>}
      <div className="flex gap-2">
        <Button type="submit" className="flex-1">
          {p.save}
        </Button>
        <Button variant="secondary" className="flex-1" onClick={onCancel}>
          {p.cancel}
        </Button>
      </div>
    </form>
  )
}

function History({ product }: { product: ProductStock }) {
  const online = useOnline()
  const [items, setItems] = useState<ProductMovement[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!online) return
    let alive = true
    api<{ items: ProductMovement[] }>(`/products/${product.recipe_id}/movements?limit=10`).then(
      (page) => alive && setItems(page.items),
      (err: unknown) => alive && setError(err instanceof ApiError ? err.userMessage : t.genericError),
    )
    return () => {
      alive = false
    }
  }, [product.recipe_id, product.stock_qty, online])
  if (!online) return <p className="mt-2 text-sm text-on-surface-variant">{p.historyOffline}</p>
  if (error) return <Alert>{error}</Alert>
  if (!items) return <Spinner label={t.loading} />
  if (items.length === 0) return <p className="mt-2 text-sm text-on-surface-variant">{p.noHistory}</p>
  return (
    <ul className="mt-2 divide-y divide-hairline text-sm">
      {items.map((m) => (
        <li key={m.id} className="flex items-baseline justify-between gap-3 py-2">
          <span>
            {p.reasons[m.reason] ?? m.reason}
            {m.note && <span className="block text-on-surface-variant">{m.note}</span>}
          </span>
          <span className="text-right">
            <Num className="block text-on-surface">{signed(m.delta_qty, product.yield_unit)}</Num>
            <Num className="block text-on-surface-variant">{formatDate(m.occurred_at)}</Num>
          </span>
        </li>
      ))}
    </ul>
  )
}

function ProductRow({ product, onAdjusted }: { product: ProductStock; onAdjusted: (delta: number) => void }) {
  const [mode, setMode] = useState<'none' | 'adjust' | 'history'>('none')
  const negative = Number(product.stock_qty) < 0
  return (
    <li className="rounded-xl border border-hairline bg-surface-container-lowest p-4">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-lg font-medium text-on-surface">{product.name}</p>
          <Num className="block text-2xl text-on-surface">{formatStock(product.stock_qty, product.yield_unit)}</Num>
          {negative && (
            <span className="mt-1 inline-flex items-center gap-1 rounded-sm bg-warning-container px-2 py-0.5 text-sm font-medium text-on-warning-container">
              <Icon name="warning" className="h-4 w-4" />
              {p.negative}
            </span>
          )}
        </div>
        <Button variant="secondary" onClick={() => setMode(mode === 'adjust' ? 'none' : 'adjust')}>
          {p.adjust}
        </Button>
      </div>
      {mode === 'adjust' && (
        <AdjustForm
          product={product}
          onCancel={() => setMode('none')}
          onDone={(delta) => {
            setMode('none')
            onAdjusted(delta)
          }}
        />
      )}
      <Button variant="ghost" className="mt-1 -ml-3" onClick={() => setMode(mode === 'history' ? 'none' : 'history')}>
        {mode === 'history' ? p.hideHistory : p.history}
      </Button>
      {mode === 'history' && <History product={product} />}
    </li>
  )
}

/** Producción reciente con "Anular" para la dueña: devuelve los insumos y resta lo que se sumó. */
function RecentProductions({ onVoided }: { onVoided: () => void }) {
  const online = useOnline()
  const { user } = useAuth()
  const owner = user?.role === 'owner'
  const [items, setItems] = useState<Production[] | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [message, setMessage] = useState<{ kind: 'info' | 'error'; text: string } | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!online) return
    let alive = true
    api<{ items: Production[] }>('/vision/productions?limit=10').then(
      (page) => alive && setItems(page.items),
      () => alive && setItems([]),
    )
    return () => {
      alive = false
    }
  }, [online, tick])

  async function voidOne(id: string) {
    setMessage(null)
    try {
      await post<Production>(`/vision/productions/${id}/void`, {})
      setConfirming(null)
      setMessage({ kind: 'info', text: p.voidDone })
      setTick((n) => n + 1)
      onVoided()
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof ApiError ? err.userMessage : t.genericError })
    }
  }

  return (
    <section aria-labelledby="productions-title" className="mt-6">
      <h2 id="productions-title" className="mb-3 font-display text-xl text-on-surface">
        {p.productions}
      </h2>
      {message && (
        <div className="mb-3">
          <Alert kind={message.kind === 'info' ? 'info' : 'error'}>{message.text}</Alert>
        </div>
      )}
      {!online ? (
        <p className="text-on-surface-variant">{p.historyOffline}</p>
      ) : !items ? (
        <Spinner label={t.loading} />
      ) : items.length === 0 ? (
        <p className="text-on-surface-variant">{p.noProductions}</p>
      ) : (
        <ul className="divide-y divide-hairline rounded-xl border border-hairline bg-surface-container-lowest">
          {items.map((r) => (
            <li key={r.id} className="p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className={`font-medium ${r.voided_at ? 'text-on-surface-variant line-through' : 'text-on-surface'}`}>
                  {r.recipe_name}
                </span>
                <Num className="text-on-surface">{`+${r.confirmed_qty}`}</Num>
              </div>
              <p className="text-sm text-on-surface-variant">
                <Num>{formatDate(r.created_at)}</Num>
                {r.was_corrected && r.detected_qty !== null && ` · ${p.corrected(r.detected_qty)}`}
                {r.voided_at && ` · ${p.voided}`}
              </p>
              {owner && !r.voided_at && r.confirmed_qty > 0 && (
                <div className="mt-2">
                  {confirming === r.id ? (
                    <div className="space-y-2">
                      <p className="text-sm text-on-surface-variant">{p.voidHint}</p>
                      <div className="flex gap-2">
                        <Button variant="secondary" className="flex-1" onClick={() => void voidOne(r.id)}>
                          {p.voidConfirm}
                        </Button>
                        <Button variant="ghost" className="flex-1" onClick={() => setConfirming(null)}>
                          {p.cancel}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button variant="ghost" className="-ml-3" onClick={() => setConfirming(r.id)}>
                      {p.void}
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** Existencias de productos terminados (T18, ADR-011): `/inventario/productos`. */
export default function ProductsStock() {
  const { value, error, loading, reload, setData } = useCached<ProductStock[]>('products:stock', '/products/stock')
  const [notice, setNotice] = useState<string | null>(null)
  useReloadWhenSynced(reload)
  const refresh = useCallback(() => reload(), [reload])

  function adjusted(product: ProductStock, delta: number) {
    setData((all) =>
      all.map((x) => (x.recipe_id === product.recipe_id ? { ...x, stock_qty: String(Number(x.stock_qty) + delta) } : x)),
    )
    setNotice(navigator.onLine ? null : t.sync.savedLocally)
  }

  return (
    <Page title={t.inventory.title} description={p.intro} onBack={() => navigate('/')}>
      <InventoryTabs active="products" />
      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-3">
          <Alert kind="info">{notice}</Alert>
        </div>
      )}
      {error && !value ? (
        <Alert>{error.code === 'offline_no_cache' ? t.sync.noCache : error.userMessage}</Alert>
      ) : !value ? (
        loading && <Spinner label={t.loading} />
      ) : value.data.length === 0 ? (
        <p>{p.empty}</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label={p.title}>
          {value.data.map((product) => (
            <ProductRow key={product.recipe_id} product={product} onAdjusted={(d) => adjusted(product, d)} />
          ))}
        </ul>
      )}
      <RecentProductions onVoided={refresh} />
    </Page>
  )
}
