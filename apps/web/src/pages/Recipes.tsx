import { useMemo, useState } from 'react'
import { Alert, Button, Page, Spinner, inputClass } from '../components/ui'
import { formatStock, type BaseUnit } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { plain, savedAtLabel } from './Inventory'

interface RecipeItem {
  id: string
  name: string
  yield_qty?: string
  yield_unit: BaseUnit
  is_final_product?: boolean
  is_active: boolean
}

export default function Recipes() {
  const { value, error, loading } = useCached<RecipeItem[]>('recipes', '/recipes')
  const [query, setQuery] = useState('')
  const items = useMemo(() => {
    const q = plain(query)
    return (value?.data ?? [])
      .filter((r) => r.is_active && (!q || plain(r.name).includes(q)))
      .sort((a, b) => a.name.localeCompare(b.name, 'es'))
  }, [value, query])

  return (
    <Page title={t.recipes.title} onBack={() => navigate('/')}>
      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      <Button className="mb-4 w-full" onClick={() => navigate('/recetas/nueva')}>
        {t.recipeForm.open}
      </Button>
      <label htmlFor="recipes-search" className="mb-1 block font-medium text-on-surface">
        {t.recipes.search}
      </label>
      <input
        id="recipes-search"
        type="search"
        className={inputClass}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoComplete="off"
      />
      {error && !value ? (
        <div className="mt-4">
          <Alert>{error.code === 'offline_no_cache' ? t.sync.noCache : error.userMessage}</Alert>
        </div>
      ) : !value ? (
        loading && <Spinner label={t.loading} />
      ) : items.length === 0 ? (
        <p className="mt-4">{t.recipes.empty}</p>
      ) : (
        <ul className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => navigate(`/recetas/${r.id}`)}
                className="block min-h-12 w-full rounded-xl bg-surface-container-lowest p-4 text-left border border-outline-variant focus-visible:ring-4 focus-visible:ring-primary/40"
              >
                <span className="block text-lg font-medium text-on-surface">{r.name}</span>
                <span className="block text-on-surface-variant">
                  {r.yield_qty && t.recipes.yields(formatStock(r.yield_qty, r.yield_unit))}
                  {r.is_final_product && ` · ${t.recipes.finalProduct}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
