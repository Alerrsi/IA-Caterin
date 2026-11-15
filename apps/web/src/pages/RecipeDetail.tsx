import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api, patch, uploadImage, type RecipeCost, type RecipeDetail as Recipe } from '../api'
import { useAuth } from '../auth'
import { ImagePicker } from '../components/ImagePicker'
import { Alert, Button, Field, Page, Spinner, inputClass, useOnline } from '../components/ui'
import { formatCLP, formatDate, formatQty, formatStock, parseQtyInput } from '../format'
import { t } from '../i18n'
import { patchCached, useCached } from '../offline/cache'
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
    <section className="mt-4 rounded-xl bg-surface-container-lowest p-4 border border-hairline">
      <h2 className="mb-2 text-lg font-medium text-on-surface">{t.recipes.costTitle}</h2>
      {!online ? (
        <p className="text-on-surface-variant">{t.recipes.costNeedsNetwork}</p>
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
              <p className="text-on-surface-variant">{t.recipes.total}</p>
              <p className="num text-3xl text-on-surface" data-testid="recipe-cost-total">
                {formatCLP(cost.total_clp)}
              </p>
              {cost.per_unit_clp !== null && (
                <p className="text-on-surface">
                  {t.recipes.perUnit}: <span className="num">{formatCLP(cost.per_unit_clp)}</span>
                </p>
              )}
              {!cost.is_complete && (
                <div className="mt-2">
                  <Alert kind="warning">{t.recipes.missing(cost.missing_prices.join(', '))}</Alert>
                </div>
              )}
              <ul className="mt-3 divide-y divide-hairline">
                {cost.lines.map((l) => (
                  <li key={l.ingredient_name} className="flex justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block font-medium">
                        {l.ingredient_name} · <span className="num font-normal">{formatStock(l.required_qty, l.base_unit)}</span>
                      </span>
                      {l.supplier_name && (
                        <span className="block text-sm text-on-surface-variant">
                          {t.recipes.from(l.supplier_name, formatDate(l.price_date))}
                        </span>
                      )}
                    </span>
                    <span className={`shrink-0 ${l.cost_clp === null ? 'font-medium' : 'num'}`}>
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

/** Cómo ven los clientes este producto en el catálogo del portal (ADR-009). Solo la dueña lo edita. */
function CatalogPanel({ recipe: initial }: { recipe: Recipe }) {
  const online = useOnline()
  const [recipe, setRecipe] = useState(initial)
  const [form, setForm] = useState({
    description: initial.catalog_description ?? '',
    category: initial.category ?? '',
    visible: initial.visible_in_catalog ?? true,
  })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  function keep(out: Recipe) {
    setRecipe(out)
    void patchCached<Recipe>(`recipe:${out.id}`, () => out)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      keep(
        await patch<Recipe>(`/recipes/${recipe.id}`, {
          catalog_description: form.description.trim() || null,
          category: form.category.trim() || null,
          visible_in_catalog: form.visible,
        }),
      )
      setSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  const set = (field: keyof typeof form) => (value: string | boolean) => {
    setSaved(false)
    setForm((f) => ({ ...f, [field]: value }))
  }

  return (
    <section className="mt-4 space-y-4 rounded-xl border border-hairline bg-surface-container-lowest p-4">
      <div>
        <h2 className="text-lg font-medium text-on-surface">{t.catalogAdmin.recipeTitle}</h2>
        <p className="text-on-surface-variant">{t.catalogAdmin.recipeHint}</p>
      </div>
      <ImagePicker
        label={t.catalogAdmin.photo}
        url={recipe.photo_url}
        disabled={!online}
        onUpload={async (file) => keep(await uploadImage<Recipe>(`/recipes/${recipe.id}/photo`, file, file.name))}
        onRemove={async () => keep(await api<Recipe>(`/recipes/${recipe.id}/photo`, { method: 'DELETE' }))}
      />
      <form onSubmit={save} className="space-y-3" noValidate>
        <Field label={t.catalogAdmin.productDescription}>
          <textarea
            className={`${inputClass} min-h-20`}
            maxLength={500}
            value={form.description}
            onChange={(e) => set('description')(e.target.value)}
          />
        </Field>
        <Field label={t.catalogAdmin.category} hint={t.catalogAdmin.categoryHint}>
          <input
            className={inputClass}
            maxLength={60}
            value={form.category}
            onChange={(e) => set('category')(e.target.value)}
          />
        </Field>
        <label className="flex min-h-12 items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-6 w-6 accent-primary"
            checked={form.visible}
            onChange={(e) => set('visible')(e.target.checked)}
          />
          <span>
            <span className="block font-medium text-on-surface">{t.catalogAdmin.visible}</span>
            <span className="block text-sm text-on-surface-variant">{t.catalogAdmin.visibleHint}</span>
          </span>
        </label>
        <Button type="submit" variant="secondary" disabled={busy || !online}>
          {t.catalogAdmin.saveProduct}
        </Button>
      </form>
      {saved && <Alert kind="info">{t.catalogAdmin.saved}</Alert>}
      {error && <Alert>{error}</Alert>}
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
          <section className="rounded-xl bg-surface-container-lowest p-4 border border-hairline">
            <p className="text-on-surface">
              {t.recipes.yields(formatStock(recipe.yield_qty, recipe.yield_unit))}
              {recipe.is_final_product && ` · ${t.recipes.finalProduct}`}
            </p>
            <h2 className="mt-3 mb-1 font-medium text-on-surface">{t.recipes.ingredients}</h2>
            <ul className="divide-y divide-hairline">
              {recipe.lines.map((l) => (
                <li key={l.id} className="flex justify-between gap-3 py-2">
                  <span>{l.ingredient_name}</span>
                  <span className="shrink-0 font-medium">{formatStock(l.qty, l.base_unit ?? 'unit')}</span>
                </li>
              ))}
            </ul>
            {recipe.notes && <p className="mt-3 whitespace-pre-line text-on-surface-variant">{recipe.notes}</p>}
          </section>
          {user?.role === 'owner' ? (
            <CostPanel recipe={recipe} />
          ) : (
            <p className="mt-4 text-on-surface-variant">{t.recipes.ownerOnlyCost}</p>
          )}
          {user?.role === 'owner' && recipe.is_final_product && <CatalogPanel key={recipe.id} recipe={recipe} />}
        </>
      )}
    </Page>
  )
}
