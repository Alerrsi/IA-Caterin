import { useMemo, useState } from 'react'
import { Alert, Page, Spinner, inputClass } from '../components/ui'
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
      <label htmlFor="recipes-search" className="mb-1 block font-semibold text-stone-800">
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
        <ul className="mt-4 space-y-3">
          {items.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => navigate(`/recetas/${r.id}`)}
                className="block min-h-12 w-full rounded-2xl bg-white p-4 text-left shadow-sm focus-visible:ring-4 focus-visible:ring-orange-300"
              >
                <span className="block text-lg font-bold text-stone-900">{r.name}</span>
                <span className="block text-stone-700">
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
