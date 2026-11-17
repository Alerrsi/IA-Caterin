import { useId, useMemo, useRef, useState } from 'react'
import { api, loadAllIngredients, type Ingredient, type OrderOut, type PortalProduct, type PortalPyme, type ProductStock } from '../api'
import { formatDate, formatStock } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { search, type FindGroup, type FindItem } from '../quickfind'
import { navigate } from '../router'
import { Dialog } from './Dialog'
import { Icon, type IconName } from './Icon'

interface RecipeLite {
  id: string
  name: string
  is_active: boolean
  category?: string | null
}

const GROUP_ICON: Record<FindGroup, IconName> = {
  actions: 'check',
  ingredients: 'inventory',
  recipes: 'restaurant',
  products: 'cloche',
  orders: 'orders',
  pymes: 'store',
  catalog: 'cloche',
}

/** Acciones y pantallas que el buscador encuentra, según el rol (las mismas reglas que la navegación). */
export function actionsFor(role: string | undefined): (FindItem & { icon: IconName })[] {
  const k = t.find.keywords
  const a = (id: string, label: string, path: string, icon: IconName, keywords = ''): FindItem & { icon: IconName } => ({
    id: `action:${id}`,
    group: 'actions',
    label,
    path,
    icon,
    keywords,
  })
  if (role === 'customer') {
    return [
      a('newQuote', t.nav.newQuote, '/cotizar', 'add', k.quote),
      a('pymes', t.nav.pymes, '/pymes', 'store', k.pymes),
      a('myQuotes', t.nav.myQuotes, '/', 'orders', k.myQuotes),
    ]
  }
  const owner = role === 'owner'
  const all: ((FindItem & { icon: IconName }) | false)[] = [
    a('quote', t.find.actions.quote, '/cotizar', 'quote', k.quote),
    a('vision', t.find.actions.vision, '/foto', 'camera', k.vision),
    a('adjust', t.find.actions.adjust, '/inventario?ajustar=1', 'inventory', k.adjust),
    a('orders', t.nav.orders, '/pedidos', 'orders', k.orders),
    a('assistant', t.nav.assistant, '/preguntar', 'chat', k.assistant),
    a('products', t.nav.products, '/inventario/productos', 'cloche', k.products),
    a('low', t.find.actions.low, '/inventario?bajo=1', 'warning', k.low),
    a('requests', t.find.actions.requests, '/pedidos?estado=requested', 'info', k.requests),
    a('upcoming', t.find.actions.upcoming, '/pedidos?proximos=7', 'orders', k.upcoming),
    a('newIngredient', t.find.actions.newIngredient, '/inventario/nuevo', 'add', k.newIngredient),
    a('newRecipe', t.find.actions.newRecipe, '/recetas/nueva', 'add', k.newRecipe),
    a('inventory', t.nav.inventory, '/inventario', 'inventory', k.inventory),
    a('recipes', t.nav.recipes, '/recetas', 'restaurant', k.recipes),
    owner && a('dashboard', t.nav.dashboard, '/tablero', 'trend', k.dashboard),
    owner && a('imports', t.nav.imports, '/importar', 'upload', k.imports),
    owner && a('metrics', t.nav.metrics, '/metricas', 'metrics', k.metrics),
    owner && a('settings', t.nav.settings, '/ajustes', 'settings', k.settings),
    a('home', t.nav.home, '/', 'home', k.home),
  ]
  return all.filter((x): x is FindItem & { icon: IconName } => x !== false)
}

/** Todos los productos de todas las pymes del directorio, para el buscador del cliente (se guarda sin red). */
async function loadPortalCatalog(): Promise<{ pyme: PortalPyme; products: PortalProduct[] }[]> {
  const pymes = await api<PortalPyme[]>('/portal/pymes')
  return Promise.all(
    pymes.map(async (pyme) => ({
      pyme,
      products: await api<PortalProduct[]>(`/portal/products?pyme_id=${encodeURIComponent(pyme.id)}`).catch(() => []),
    })),
  )
}

/** Candidatos del buscador armados con lo guardado en el teléfono (`useCached`): funciona sin red y sin IA. */
function useCandidates(role: string | undefined): { items: FindItem[]; offline: boolean } {
  const customer = role === 'customer'
  const ingredients = useCached<Ingredient[]>('ingredients', customer ? null : loadAllIngredients)
  const recipes = useCached<RecipeLite[]>('recipes', customer ? null : '/recipes')
  const products = useCached<ProductStock[]>('products:stock', customer ? null : '/products/stock')
  const orders = useCached<OrderOut[]>('orders:all', customer ? null : '/orders')
  const catalog = useCached('portal:search', customer ? loadPortalCatalog : null)

  const items = useMemo(() => {
    const out: FindItem[] = actionsFor(role).map((a) => ({ id: a.id, group: a.group, label: a.label, path: a.path, keywords: a.keywords }))
    for (const i of ingredients.value?.data ?? []) {
      if (!i.is_active) continue
      out.push({
        id: `ing:${i.id}`,
        group: 'ingredients',
        label: i.name,
        detail: t.find.stock(formatStock(i.stock_qty, i.base_unit)),
        path: `/inventario/${i.id}`,
        keywords: i.category ?? '',
      })
    }
    for (const r of recipes.value?.data ?? []) {
      if (!r.is_active) continue
      out.push({ id: `rec:${r.id}`, group: 'recipes', label: r.name, path: `/recetas/${r.id}`, keywords: r.category ?? '' })
    }
    for (const p of products.value?.data ?? []) {
      if (Number(p.stock_qty) <= 0) continue // sin existencias ya aparece como receta
      out.push({
        id: `prod:${p.recipe_id}`,
        group: 'products',
        label: p.name,
        detail: t.find.ready(formatStock(p.stock_qty, p.yield_unit)),
        path: '/inventario/productos',
      })
    }
    for (const o of orders.value?.data ?? []) {
      if (o.status === 'customer_draft') continue
      out.push({
        id: `ord:${o.id}`,
        group: 'orders',
        label: o.customer_name,
        detail: [o.event_date ? t.find.eventOn(formatDate(o.event_date)) : t.orders.noDate, t.orders.status[o.status]].join(' · '),
        path: `/pedidos?pedido=${o.id}`,
        keywords: [o.event_date ? formatDate(o.event_date) : '', t.orders.status[o.status]].join(' '),
      })
    }
    for (const { pyme, products: list } of catalog.value?.data ?? []) {
      out.push({ id: `pyme:${pyme.id}`, group: 'pymes', label: pyme.name, detail: pyme.commune ?? undefined, path: `/pymes/${pyme.id}` })
      for (const p of list) {
        out.push({
          id: `cat:${pyme.id}:${p.id}`,
          group: 'catalog',
          label: p.name,
          detail: pyme.name,
          path: `/pymes/${pyme.id}`,
          keywords: p.category ?? '',
        })
      }
    }
    return out
  }, [role, ingredients.value, recipes.value, products.value, orders.value, catalog.value])

  const offline = [ingredients, recipes, products, orders, catalog].some((c) => c.value?.fromCache)
  return { items, offline }
}

/**
 * Buscador global "¿Qué necesitas?" (T22): combobox ARIA 1.2 dentro de un diálogo. Flechas para elegir, Enter abre,
 * Esc cierra. Resultados agrupados (acciones, insumos, recetas, productos listos, pedidos; para el cliente, pymes y
 * productos), como máximo 8.
 */
export function QuickFind({ role, onClose }: { role: string | undefined; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const uid = useId()
  const { items, offline } = useCandidates(role)
  const results = useMemo(() => search(query, items), [query, items])
  const icons = useMemo(() => new Map(actionsFor(role).map((a) => [a.id, a.icon])), [role])
  const optionId = (i: number) => `${uid}-opt-${i}`

  function open(index: number) {
    const r = results[index]
    if (!r) return
    onClose()
    navigate(r.path)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (i + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (i - 1 + results.length) % results.length)
    } else if (e.key === 'Home') {
      e.preventDefault()
      setActive(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setActive(results.length - 1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      open(active)
    }
  }

  // Grupos en el orden de los resultados, con el índice global de cada opción (para aria-activedescendant).
  const groups: { group: FindGroup; rows: { item: (typeof results)[number]; index: number }[] }[] = []
  results.forEach((item, index) => {
    const last = groups[groups.length - 1]
    if (last && last.group === item.group) last.rows.push({ item, index })
    else groups.push({ group: item.group, rows: [{ item, index }] })
  })
  const listId = `${uid}-list`

  return (
    <Dialog label={t.find.label} placement="top" onClose={onClose} initialFocus={input}>
      <div className="flex items-center gap-2 border-b border-hairline px-3 py-2">
        <Icon name="search" className="ml-1 h-6 w-6 shrink-0 text-on-surface-variant" />
        <input
          ref={input}
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={results.length > 0 ? optionId(active) : undefined}
          aria-label={t.find.label}
          aria-describedby={`${uid}-hint`}
          type="text"
          inputMode="search"
          enterKeyHint="go"
          autoComplete="off"
          spellCheck={false}
          placeholder={t.find.placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
          className="min-h-14 min-w-0 flex-1 bg-transparent text-lg text-on-surface outline-none placeholder:text-on-surface-variant/80"
        />
        <button
          type="button"
          onClick={onClose}
          aria-label={t.find.close}
          className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-on-surface hover:bg-surface-container focus-visible:ring-4 focus-visible:ring-primary/40"
        >
          <Icon name="close" />
        </button>
      </div>
      <p id={`${uid}-hint`} className="px-5 pt-3 text-sm text-on-surface-variant">
        {offline ? t.find.offline : t.find.hint}
      </p>
      <p className="sr-only" aria-live="polite">
        {query ? t.find.count(results.length) : ''}
      </p>
      {results.length === 0 ? (
        <p className="px-5 py-6 text-on-surface-variant">{t.find.empty(query)}</p>
      ) : (
        <ul id={listId} role="listbox" aria-label={t.find.label} className="overflow-y-auto overscroll-contain px-2 pb-3 pt-1">
          {groups.map(({ group, rows }) => (
            <li key={group} role="presentation">
              <p id={`${uid}-g-${group}`} className="px-3 pb-1 pt-3 text-sm font-semibold text-on-surface-variant">
                {t.find.groups[group]}
              </p>
              <ul role="group" aria-labelledby={`${uid}-g-${group}`}>
                {rows.map(({ item, index }) => (
                  <li
                    key={item.id}
                    id={optionId(index)}
                    role="option"
                    aria-selected={index === active}
                    onMouseMove={() => setActive(index)}
                    onClick={() => open(index)}
                    className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl px-3 py-2 ${
                      index === active ? 'bg-accent-soft' : ''
                    }`}
                  >
                    <span
                      className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                        index === active ? 'bg-accent text-on-accent' : 'bg-surface-container text-on-surface'
                      }`}
                    >
                      <Icon name={icons.get(item.id) ?? GROUP_ICON[item.group]} className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-base font-semibold text-on-surface">{item.label}</span>
                      {item.detail && <span className="block truncate text-sm text-on-surface-variant">{item.detail}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  )
}
