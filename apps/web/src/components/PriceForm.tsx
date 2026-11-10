import { useState, type FormEvent } from 'react'
import { ApiError, api, post, type Ingredient } from '../api'
import { ADJUST_UNITS, formatCLP, formatDate, parseQtyInput } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { Alert, Button, Field, Spinner, inputClass, useOnline } from './ui'

interface Supplier {
  id: string
  name: string
  is_active: boolean
}

interface Comparison {
  items: {
    price_id: string
    supplier_name: string
    package_label: string
    price_clp: number
    includes_vat: boolean
    price_date: string
    price_per_reference_clp: string
    reference_unit: string
    is_best: boolean
  }[]
}

/** "21.000" o "$21.000" -> 21000; null si no es un entero positivo (los precios van en CLP sin decimales). */
function parseClp(raw: string): number | null {
  const digits = raw.trim().replace(/[$\s.]/g, '')
  if (!/^\d+$/.test(digits)) return null
  const n = Number(digits)
  return n > 0 ? n : null
}

function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Precios vigentes de un insumo y carga de un precio a mano (para poder cotizar sin planilla). */
export function PriceSection({ ingredient }: { ingredient: Ingredient }) {
  const online = useOnline()
  const prices = useCached<Comparison>(`prices:${ingredient.id}`, `/ingredients/${ingredient.id}/prices`)
  const [open, setOpen] = useState(false)
  const [saved, setSaved] = useState(false)

  return (
    <section className="mt-4 rounded-xl bg-surface-container-lowest p-4 border border-outline-variant" aria-labelledby={`prices-${ingredient.id}`}>
      <h2 id={`prices-${ingredient.id}`} className="mb-2 text-lg font-medium text-on-surface">
        {t.priceForm.current}
      </h2>
      {saved && (
        <div className="mb-2">
          <Alert kind="info">{t.priceForm.saved}</Alert>
        </div>
      )}
      {prices.value ? (
        prices.value.data.items.length === 0 ? (
          <p className="text-on-surface-variant">{t.priceForm.none}</p>
        ) : (
          <ul className="divide-y divide-outline-variant">
            {prices.value.data.items.map((p) => (
              <li key={p.price_id} className="py-2">
                <span className="block font-medium">
                  {p.supplier_name}
                  {p.is_best && ` · ${t.priceForm.best}`}
                </span>
                <span className="block text-on-surface-variant">
                  {p.package_label}: {formatCLP(p.price_clp)} ({formatDate(p.price_date)}) ·{' '}
                  {t.priceForm.perRef(formatCLP(Math.round(Number(p.price_per_reference_clp))), p.reference_unit)}
                </span>
              </li>
            ))}
          </ul>
        )
      ) : prices.error ? (
        <p className="text-on-surface-variant">{prices.error.status === 0 ? t.priceForm.needsNetwork : prices.error.userMessage}</p>
      ) : (
        <Spinner label={t.loading} />
      )}
      {open ? (
        <PriceForm
          ingredient={ingredient}
          onCancel={() => setOpen(false)}
          onSaved={() => {
            setOpen(false)
            setSaved(true)
            prices.reload()
          }}
        />
      ) : (
        <Button
          variant="secondary"
          className="mt-3 w-full"
          disabled={!online}
          onClick={() => {
            setSaved(false)
            setOpen(true)
          }}
        >
          {t.priceForm.open}
        </Button>
      )}
    </section>
  )
}

const NEW = '__new__'

function PriceForm({ ingredient, onSaved, onCancel }: { ingredient: Ingredient; onSaved: () => void; onCancel: () => void }) {
  const suppliers = useCached<Supplier[]>('suppliers', '/suppliers')
  const units = ADJUST_UNITS[ingredient.base_unit]
  const active = (suppliers.value?.data ?? []).filter((s) => s.is_active)
  const [supplierId, setSupplierId] = useState('')
  const [newName, setNewName] = useState('')
  const [label, setLabel] = useState('')
  const [qty, setQty] = useState('')
  const [unit, setUnit] = useState(units[0].value)
  const [price, setPrice] = useState('')
  const [vat, setVat] = useState(true)
  const [date, setDate] = useState(today)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const creating = supplierId === NEW || (active.length === 0 && suppliers.value !== null)

  async function save(e: FormEvent) {
    e.preventDefault()
    if (creating ? newName.trim().length < 2 : !supplierId) return setError(t.priceForm.errSupplier)
    const packageQty = parseQtyInput(qty)
    if (!label.trim() || !packageQty) return setError(t.priceForm.errPackage)
    const clp = parseClp(price)
    if (clp === null) return setError(t.priceForm.errPrice)
    setError(null)
    setSaving(true)
    try {
      let sid = supplierId
      if (creating) sid = (await post<Supplier>('/suppliers', { name: newName.trim() })).id
      await api('/prices', {
        method: 'POST',
        body: JSON.stringify({
          ingredient_id: ingredient.id,
          supplier_id: sid,
          package_label: label.trim(),
          package_qty: packageQty,
          package_unit: unit,
          price_clp: clp,
          includes_vat: vat,
          price_date: date,
        }),
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="mt-4 space-y-3 border-t-2 border-outline-variant pt-4" noValidate>
      {active.length > 0 && (
        <Field label={t.priceForm.supplier}>
          <select className={inputClass} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">{t.priceForm.chooseSupplier}</option>
            {active.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
            <option value={NEW}>{t.priceForm.newSupplier}</option>
          </select>
        </Field>
      )}
      {creating && (
        <Field label={t.priceForm.newSupplierName}>
          <input className={inputClass} value={newName} maxLength={120} onChange={(e) => setNewName(e.target.value)} />
        </Field>
      )}
      <Field label={t.priceForm.packageLabel}>
        <input
          className={inputClass}
          value={label}
          maxLength={80}
          placeholder={t.priceForm.packagePlaceholder}
          onChange={(e) => setLabel(e.target.value)}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.priceForm.packageQty}>
          <input className={inputClass} inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} />
        </Field>
        <Field label={t.priceForm.packageUnit}>
          <select className={inputClass} value={unit} onChange={(e) => setUnit(e.target.value)}>
            {units.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label={t.priceForm.price}>
        <input className={inputClass} inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} />
      </Field>
      <label className="flex min-h-12 items-center gap-3 text-lg">
        <input
          type="checkbox"
          className="h-6 w-6 shrink-0 accent-primary"
          checked={vat}
          onChange={(e) => setVat(e.target.checked)}
        />
        {t.priceForm.includesVat}
      </label>
      <Field label={t.priceForm.date}>
        <input type="date" className={inputClass} value={date} max={today()} onChange={(e) => setDate(e.target.value)} />
      </Field>
      {error && <Alert>{error}</Alert>}
      <div className="flex gap-3">
        <Button variant="secondary" className="flex-1" onClick={onCancel}>
          {t.priceForm.cancel}
        </Button>
        <Button type="submit" className="flex-1" disabled={saving}>
          {saving ? t.priceForm.saving : t.priceForm.save}
        </Button>
      </div>
    </form>
  )
}
