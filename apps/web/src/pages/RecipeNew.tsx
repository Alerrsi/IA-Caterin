import { useMemo, useRef, useState, type FormEvent } from 'react'
import { ApiError, loadAllIngredients, post, type Ingredient, type RecipeDetail } from '../api'
import { Alert, Button, Field, Page, Spinner, inputClass, useOnline } from '../components/ui'
import { ADJUST_UNITS, parseQtyInput } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { plain } from './Inventory'

interface Line {
  key: number
  search: string
  ingredientId: string
  qty: string
  unit: string
  waste: string
}

/** Rendimiento: lo que elige la usuaria → unidad base de la receta y factor. */
const YIELD_UNITS: { value: string; base: 'unit' | 'g' | 'ml'; factor: number }[] = [
  { value: 'unit', base: 'unit', factor: 1 },
  { value: 'kg', base: 'g', factor: 1000 },
  { value: 'g', base: 'g', factor: 1 },
  { value: 'l', base: 'ml', factor: 1000 },
  { value: 'ml', base: 'ml', factor: 1 },
]

function scaled(qty: string, factor: number): string {
  // Decimal en texto sin pasar por float cuando el factor es 1; con 1000 basta con mover la coma.
  if (factor === 1) return qty
  return (Number(qty) * factor).toFixed(3).replace(/\.?0+$/, '')
}

function LineEditor({
  n,
  line,
  ingredients,
  onChange,
  onRemove,
}: {
  n: number
  line: Line
  ingredients: Ingredient[]
  onChange: (patch: Partial<Line>) => void
  onRemove?: () => void
}) {
  const q = plain(line.search)
  const options = ingredients.filter((i) => !q || plain(i.name).includes(q) || i.id === line.ingredientId)
  const chosen = ingredients.find((i) => i.id === line.ingredientId)
  const units = chosen ? ADJUST_UNITS[chosen.base_unit] : []
  return (
    <fieldset className="space-y-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
      <legend className="px-1 font-medium text-on-surface">{t.recipeForm.line(n)}</legend>
      <Field label={t.recipeForm.search}>
        <input
          type="search"
          className={inputClass}
          value={line.search}
          autoComplete="off"
          onChange={(e) => onChange({ search: e.target.value })}
        />
      </Field>
      <Field label={t.recipeForm.ingredient}>
        <select
          className={inputClass}
          value={line.ingredientId}
          onChange={(e) => {
            const ing = ingredients.find((i) => i.id === e.target.value)
            onChange({ ingredientId: e.target.value, unit: ing ? ADJUST_UNITS[ing.base_unit][0].value : '' })
          }}
        >
          <option value="">{t.recipeForm.chooseIngredient}</option>
          {options.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.recipeForm.qty}>
          <input
            className={inputClass}
            inputMode="decimal"
            value={line.qty}
            autoComplete="off"
            onChange={(e) => onChange({ qty: e.target.value })}
          />
        </Field>
        <Field label={t.recipeForm.unit}>
          <select
            className={inputClass}
            value={line.unit}
            disabled={!chosen}
            onChange={(e) => onChange({ unit: e.target.value })}
          >
            {units.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label={t.recipeForm.waste}>
        <input
          className={inputClass}
          inputMode="decimal"
          value={line.waste}
          autoComplete="off"
          onChange={(e) => onChange({ waste: e.target.value })}
        />
      </Field>
      {onRemove && (
        <Button variant="ghost" onClick={onRemove}>
          {t.recipeForm.removeLine(n)}
        </Button>
      )}
    </fieldset>
  )
}

export default function RecipeNew() {
  const online = useOnline()
  const ingredients = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const active = useMemo(
    () =>
      (ingredients.value?.data ?? []).filter((i) => i.is_active).sort((a, b) => a.name.localeCompare(b.name, 'es')),
    [ingredients.value],
  )
  const nextKey = useRef(2)
  const [name, setName] = useState('')
  const [yieldQty, setYieldQty] = useState('')
  const [yieldUnit, setYieldUnit] = useState('unit')
  const [finalProduct, setFinalProduct] = useState(true)
  const [visionClass, setVisionClass] = useState('')
  const [lines, setLines] = useState<Line[]>([{ key: 1, search: '', ingredientId: '', qty: '', unit: '', waste: '' }])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const patch = (key: number, p: Partial<Line>) => setLines((all) => all.map((l) => (l.key === key ? { ...l, ...p } : l)))

  function validate(): string | null {
    if (name.trim().length < 2) return t.recipeForm.errName
    if (!parseQtyInput(yieldQty)) return t.recipeForm.errYield
    if (lines.length === 0) return t.recipeForm.errLines
    const seen = new Set<string>()
    for (const [i, l] of lines.entries()) {
      if (!l.ingredientId) return t.recipeForm.errLineIngredient(i + 1)
      if (!parseQtyInput(l.qty)) return t.recipeForm.errLineQty(i + 1)
      if (l.waste.trim()) {
        const w = Number(l.waste.trim().replace(',', '.'))
        if (!Number.isFinite(w) || w < 0 || w > 100) return t.recipeForm.errLineWaste(i + 1)
      }
      if (seen.has(l.ingredientId)) {
        return t.recipeForm.errDuplicate(active.find((x) => x.id === l.ingredientId)?.name ?? '')
      }
      seen.add(l.ingredientId)
    }
    return null
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    const problem = validate()
    setError(problem)
    if (problem) return
    const yu = YIELD_UNITS.find((u) => u.value === yieldUnit) ?? YIELD_UNITS[0]
    setSaving(true)
    try {
      const created = await post<RecipeDetail>('/recipes', {
        name: name.trim(),
        yield_qty: scaled(parseQtyInput(yieldQty)!, yu.factor),
        yield_unit: yu.base,
        is_final_product: finalProduct,
        vision_class: visionClass.trim() || null,
        lines: lines.map((l) => ({
          ingredient_id: l.ingredientId,
          qty: parseQtyInput(l.qty),
          unit: l.unit || null,
          waste_pct: l.waste.trim() ? l.waste.trim().replace(',', '.') : null,
        })),
      })
      navigate(`/recetas/${created.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
      setSaving(false)
    }
  }

  return (
    <Page title={t.recipeForm.title} onBack={() => navigate('/recetas')} size="narrow">
      {!online && (
        <div className="mb-4">
          <Alert kind="warning">{t.sync.needsNetwork}</Alert>
        </div>
      )}
      {!ingredients.value && ingredients.loading ? (
        <Spinner label={t.loading} />
      ) : active.length === 0 ? (
        <Alert kind="info">{t.recipeForm.noIngredients}</Alert>
      ) : (
        <form onSubmit={save} className="space-y-4" noValidate>
          <Field label={t.recipeForm.name}>
            <input
              className={inputClass}
              value={name}
              maxLength={120}
              placeholder={t.recipeForm.namePlaceholder}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t.recipeForm.yieldQty}>
              <input
                className={inputClass}
                inputMode="decimal"
                value={yieldQty}
                autoComplete="off"
                onChange={(e) => setYieldQty(e.target.value)}
              />
            </Field>
            <Field label={t.recipeForm.yieldUnit}>
              <select className={inputClass} value={yieldUnit} onChange={(e) => setYieldUnit(e.target.value)}>
                {YIELD_UNITS.map((u) => (
                  <option key={u.value} value={u.value}>
                    {t.recipeForm.yieldUnits[u.value]}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <label className="flex min-h-12 items-center gap-3 text-lg">
            <input
              type="checkbox"
              className="h-6 w-6 shrink-0 accent-primary"
              checked={finalProduct}
              onChange={(e) => setFinalProduct(e.target.checked)}
            />
            {t.recipeForm.finalProduct}
          </label>
          {finalProduct && (
            <Field label={t.recipeForm.visionClass} hint={t.recipeForm.visionClassHint}>
              <input
                className={inputClass}
                value={visionClass}
                maxLength={60}
                autoComplete="off"
                onChange={(e) => setVisionClass(e.target.value)}
              />
            </Field>
          )}
          <h2 className="pt-2 text-lg font-medium text-on-surface">{t.recipeForm.lines}</h2>
          {lines.map((l, i) => (
            <LineEditor
              key={l.key}
              n={i + 1}
              line={l}
              ingredients={active}
              onChange={(p) => patch(l.key, p)}
              onRemove={lines.length > 1 ? () => setLines((all) => all.filter((x) => x.key !== l.key)) : undefined}
            />
          ))}
          <Button
            variant="secondary"
            className="w-full"
            onClick={() =>
              setLines((all) => [
                ...all,
                { key: nextKey.current++, search: '', ingredientId: '', qty: '', unit: '', waste: '' },
              ])
            }
          >
            {t.recipeForm.addLine}
          </Button>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" className="w-full" disabled={saving || !online}>
            {saving ? t.recipeForm.saving : t.recipeForm.save}
          </Button>
        </form>
      )}
    </Page>
  )
}
