import { useState, type FormEvent } from 'react'
import { ApiError, post, type BaseUnitCode, type Ingredient } from '../api'
import { Alert, Button, Field, inputClass, Page, useOnline } from '../components/ui'
import { ADJUST_UNITS, parseQtyInput } from '../format'
import { t } from '../i18n'
import { patchCached } from '../offline/cache'
import { navigate } from '../router'

const BASES: BaseUnitCode[] = ['g', 'ml', 'unit']

/** "2,5" en kg -> "2500.000" g. null si no es un número de 0 o más; '' si el campo va vacío. */
function toBase(raw: string, factor: number): string | null {
  if (!raw.trim()) return ''
  const parsed = parseQtyInput(raw)
  const n = parsed === null ? NaN : Number(parsed)
  return n >= 0 ? (n * factor).toFixed(3) : null
}

export default function IngredientNew() {
  const online = useOnline()
  const [name, setName] = useState('')
  const [base, setBase] = useState<BaseUnitCode>('g')
  const [unit, setUnit] = useState(ADJUST_UNITS.g[0].value)
  const [stock, setStock] = useState('')
  const [min, setMin] = useState('')
  const [waste, setWaste] = useState('')
  const [category, setCategory] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function changeBase(b: BaseUnitCode) {
    setBase(b)
    setUnit(ADJUST_UNITS[b][0].value)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (name.trim().length < 2) return setError(t.ingredientForm.badName)
    const factor = ADJUST_UNITS[base].find((u) => u.value === unit)?.factor ?? 1
    const initial = toBase(stock, factor)
    const minimum = toBase(min, factor)
    if (initial === null || minimum === null) return setError(t.ingredientForm.badQty)
    let wastePct: string | null = null
    if (waste.trim()) {
      const w = parseQtyInput(waste)
      if (w === null || !(Number(w) >= 0 && Number(w) < 100)) return setError(t.ingredientForm.badWaste)
      wastePct = w
    }
    setBusy(true)
    try {
      const created = await post<Ingredient>('/ingredients', {
        name: name.trim(),
        base_unit: base,
        initial_stock: initial || '0',
        min_stock_qty: minimum || null,
        waste_pct: wastePct,
        category: category.trim() || null,
      })
      await patchCached<Ingredient[]>('ingredients', (all) => [...all.filter((i) => i.id !== created.id), created])
      navigate(`/inventario/${created.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
      setBusy(false)
    }
  }

  return (
    <Page title={t.ingredientForm.title} onBack={() => navigate('/inventario')} size="narrow">
      {!online && (
        <div className="mb-4">
          <Alert kind="warning">{t.ingredientForm.needsNetwork}</Alert>
        </div>
      )}
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label={t.ingredientForm.name}>
          <input
            className={inputClass}
            value={name}
            maxLength={120}
            placeholder={t.ingredientForm.namePlaceholder}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <fieldset>
          <legend className="mb-1 font-medium text-on-surface">{t.ingredientForm.baseUnit}</legend>
          <div className="space-y-1">
            {BASES.map((b) => (
              <label key={b} className="flex min-h-12 items-center gap-3 text-lg">
                <input
                  type="radio"
                  name="base-unit"
                  className="h-6 w-6 accent-primary"
                  checked={base === b}
                  onChange={() => changeBase(b)}
                />
                {t.ingredientForm.baseUnits[b]}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.ingredientForm.stock}>
            <input className={inputClass} inputMode="decimal" value={stock} onChange={(e) => setStock(e.target.value)} />
          </Field>
          <Field label={t.ingredientForm.unit}>
            <select className={inputClass} value={unit} onChange={(e) => setUnit(e.target.value)}>
              {ADJUST_UNITS[base].map((u) => (
                <option key={u.value} value={u.value}>
                  {u.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label={t.ingredientForm.min}>
          <input className={inputClass} inputMode="decimal" value={min} onChange={(e) => setMin(e.target.value)} />
        </Field>
        <Field label={t.ingredientForm.waste} hint={t.ingredientForm.wasteHint}>
          <input className={inputClass} inputMode="decimal" value={waste} onChange={(e) => setWaste(e.target.value)} />
        </Field>
        <Field label={t.ingredientForm.category}>
          <input
            className={inputClass}
            value={category}
            maxLength={60}
            placeholder={t.ingredientForm.categoryPlaceholder}
            onChange={(e) => setCategory(e.target.value)}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" className="w-full" disabled={busy || !online}>
          {busy ? t.ingredientForm.saving : t.ingredientForm.save}
        </Button>
      </form>
    </Page>
  )
}
