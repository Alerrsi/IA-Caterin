import { useState, type FormEvent } from 'react'
import type { Ingredient } from '../api'
import { ADJUST_UNITS, parseQtyInput } from '../format'
import { t } from '../i18n'
import { enqueue } from '../offline/queue'
import { Alert, Button, Field, inputClass } from './ui'

const REASONS: Record<1 | -1, string[]> = {
  1: ['purchase', 'adjustment'],
  [-1]: ['consumption', 'waste', 'adjustment'],
}

/** Ingrediente con el delta (en unidad base) ya aplicado: para mostrar el cambio sin esperar a la red. */
export function applyDelta(ing: Ingredient, deltaBase: number): Ingredient {
  const stock = Number(ing.stock_qty) + deltaBase
  const min = ing.min_stock_qty === null ? null : Number(ing.min_stock_qty)
  return { ...ing, stock_qty: stock.toFixed(3), is_low: min !== null && stock < min }
}

/**
 * Panel de ajuste de stock (ADR-004): el movimiento se encola con su Idempotency-Key y se envía apenas haya
 * señal. `onDone` recibe el cambio en unidad base para actualizar la pantalla de inmediato.
 */
export function StockAdjust({
  ingredient,
  sign,
  onDone,
  onCancel,
}: {
  ingredient: Ingredient
  sign: 1 | -1
  onDone: (deltaBase: number) => void
  onCancel: () => void
}) {
  const units = ADJUST_UNITS[ingredient.base_unit]
  const [amount, setAmount] = useState('')
  const [unit, setUnit] = useState(units[0].value)
  const [reason, setReason] = useState(REASONS[sign][0])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const idBase = `adj-${ingredient.id}`

  async function save(e: FormEvent) {
    e.preventDefault()
    const qty = parseQtyInput(amount)
    if (!qty) {
      setError(t.inventory.badAmount)
      return
    }
    const u = units.find((x) => x.value === unit) ?? units[0]
    const signed = sign < 0 ? `-${qty}` : qty
    setSaving(true)
    await enqueue({
      path: '/stock/movements',
      body: {
        ingredient_id: ingredient.id,
        reason,
        delta_qty: signed,
        unit: u.value,
        occurred_at: new Date().toISOString(),
      },
      label: `${ingredient.name}: ${sign < 0 ? '−' : '+'}${amount.trim()} ${u.label}`,
    })
    setSaving(false)
    onDone(sign * Number(qty) * u.factor)
  }

  return (
    <form onSubmit={save} className="mt-3 space-y-3 rounded-xl bg-surface-container p-3">
      {error && <Alert>{error}</Alert>}
      <div className="flex gap-2">
        <div className="min-w-0 flex-1">
          <Field label={t.inventory.amount}>
            <input
              id={`${idBase}-qty`}
              className={inputClass}
              inputMode="decimal"
              autoComplete="off"
              autoFocus
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </Field>
        </div>
        <div className="w-32 shrink-0">
          <Field label={t.inventory.unit}>
            <select className={inputClass} value={unit} onChange={(e) => setUnit(e.target.value)}>
              {units.map((u) => (
                <option key={u.value} value={u.value}>
                  {u.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </div>
      <Field label={t.inventory.reason}>
        <select className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)}>
          {REASONS[sign].map((r) => (
            <option key={r} value={r}>
              {t.inventory.reasons[r]}
            </option>
          ))}
        </select>
      </Field>
      <div className="flex gap-2">
        <Button type="submit" className="flex-1" disabled={saving}>
          {t.inventory.save}
        </Button>
        <Button variant="secondary" className="flex-1" onClick={onCancel}>
          {t.inventory.cancel}
        </Button>
      </div>
    </form>
  )
}
