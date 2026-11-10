import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api, type RecipeCost, type RecipeDetail as Recipe } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, Page, Spinner, inputClass, useOnline } from '../components/ui'
import { formatCLP, formatDate, formatQty, formatStock, parseQtyInput } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { savedAtLabel } from './Inventory'

function CostPanel({ recipe }: { recipe: Recipe }) {
  const online = useOnline()
  const [qty, setQty] = useState(() => formatQty(recipe.yield_qty))
  const [cost, setCost] = useState<RecipeCost | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [asked, setAsked] = useState<string | null>(online ? recipe.yield_qty : null)

  useEffect(() => {
    if (asked === null) return
    let alive = true
    api<RecipeCost>(`/recipes/${recipe.id}/cost?qty=${encodeURIComponent(asked)}`).then(
      (c) => {
        if (!alive) return
        setCost(c)
        setError(null)
        setBusy(false)
      },
      (err: unknown) => {
        if (!alive) return
        setError(err instanceof ApiError ? err.userMessage : t.genericError)
        setBusy(false)
      },
    )
    return () => {
      alive = false
    }
  }, [asked, recipe.id])

  function submit(e: FormEvent) {
    e.preventDefault()
    const q = parseQtyInput(qty)
    if (!q) {
      setError(t.inventory.badAmount)
      return
    }
    setBusy(true)
    setAsked(q)
  }

  return (
    <section className="mt-4 rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-lg font-bold text-stone-900">{t.recipes.costTitle}</h2>
      {!online ? (
        <p className="text-stone-700">{t.recipes.costNeedsNetwork}</p>
      ) : (
        <>
          <form onSubmit={submit} className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <Field label={t.recipes.costFor}>
                <input className={inputClass} inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} />
              </Field>
            </div>
            <Button type="submit" className="shrink-0" disabled={busy}>
              {t.recipes.calc}
            </Button>
          </form>
          {error && (
            <div className="mt-3">
              <Alert>{error}</Alert>
            </div>
          )}
          {cost && (
            <div className="mt-3">
              <p className="text-stone-700">{t.recipes.total}</p>
              <p className="text-3xl font-bold text-stone-900" data-testid="recipe-cost-total">
                {formatCLP(cost.total_clp)}
              </p>
              {cost.per_unit_clp !== null && (
                <p className="text-stone-800">
                  {t.recipes.perUnit}: {formatCLP(cost.per_unit_clp)}
                </p>
              )}
              {!cost.is_complete && (
                <div className="mt-2">
                  <Alert kind="warning">{t.recipes.missing(cost.missing_prices.join(', '))}</Alert>
                </div>
              )}
              <ul className="mt-3 divide-y divide-stone-200">
                {cost.lines.map((l) => (
                  <li key={l.ingredient_name} className="flex justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block font-semibold">
                        {l.ingredient_name} · {formatStock(l.required_qty, l.base_unit)}
                      </span>
                      {l.supplier_name && (
                        <span className="block text-sm text-stone-700">
                          {t.recipes.from(l.supplier_name, formatDate(l.price_date))}
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 font-semibold">
                      {l.cost_clp === null ? t.recipes.noPrice : formatCLP(l.cost_clp)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}

export default function RecipeDetail({ id }: { id: string }) {
  const { user } = useAuth()
  const { value, error, loading } = useCached<Recipe>(`recipe:${id}`, `/recipes/${id}`)
  const recipe = value?.data

  return (
    <Page title={recipe?.name ?? t.recipes.title} onBack={() => navigate('/recetas')}>
      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      {!recipe ? (
        error ? (
          <Alert>{error.code === 'offline_no_cache' ? t.sync.noCache : error.userMessage}</Alert>
        ) : (
          loading && <Spinner label={t.loading} />
        )
      ) : (
        <>
          <section className="rounded-2xl bg-white p-4 shadow-sm">
            <p className="text-stone-800">
              {t.recipes.yields(formatStock(recipe.yield_qty, recipe.yield_unit))}
              {recipe.is_final_product && ` · ${t.recipes.finalProduct}`}
            </p>
            <h2 className="mt-3 mb-1 font-bold text-stone-900">{t.recipes.ingredients}</h2>
            <ul className="divide-y divide-stone-200">
              {recipe.lines.map((l) => (
                <li key={l.id} className="flex justify-between gap-3 py-2">
                  <span>{l.ingredient_name}</span>
                  <span className="shrink-0 font-semibold">{formatStock(l.qty, l.base_unit ?? 'unit')}</span>
                </li>
              ))}
            </ul>
            {recipe.notes && <p className="mt-3 whitespace-pre-line text-stone-700">{recipe.notes}</p>}
          </section>
          {user?.role === 'owner' ? (
            <CostPanel recipe={recipe} />
          ) : (
            <p className="mt-4 text-stone-700">{t.recipes.ownerOnlyCost}</p>
          )}
        </>
      )}
    </Page>
  )
}
