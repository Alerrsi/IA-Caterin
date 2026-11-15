import { useMemo, useState } from 'react'
import type { PortalProduct, PortalPyme as Pyme } from '../../api'
import { Alert, Button, Page, Spinner } from '../../components/ui'
import { Icon } from '../../components/Icon'
import { t } from '../../i18n'
import { useCached } from '../../offline/cache'
import { navigate } from '../../router'
import { savedAtLabel } from '../Inventory'
import { PymeAvatar } from './PortalPymes'

/** Ruta a cotizar con esta pyme y los productos marcados (los lee `NewQuote`). */
export function quotePath(pymeId: string, picked: string[]): string {
  return `/cotizar?pyme=${encodeURIComponent(pymeId)}${picked.length ? `&p=${picked.map(encodeURIComponent).join(',')}` : ''}`
}

function ProductCard({ product, added, onToggle }: { product: PortalProduct; added: boolean; onToggle: () => void }) {
  // Celular: fila compacta con miniatura. Desde 640 px: tarjeta con la foto arriba.
  return (
    <li className="flex gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 sm:flex-col sm:gap-0 sm:overflow-hidden sm:p-0">
      {product.photo_url ? (
        <img
          src={product.photo_url}
          alt=""
          loading="lazy"
          className="h-20 w-20 shrink-0 rounded-lg object-cover sm:aspect-[4/3] sm:h-auto sm:w-full sm:rounded-none"
        />
      ) : (
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-surface-container-high text-on-surface-variant sm:aspect-[4/3] sm:h-auto sm:w-full sm:rounded-none">
          <Icon name="cloche" className="h-9 w-9 sm:h-12 sm:w-12" />
          <span className="sr-only">{t.catalog.noPhoto}</span>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col sm:p-4">
        <h3 className="text-lg font-medium text-on-surface">{product.name}</h3>
        <p className="text-sm text-on-surface-variant">{t.catalog.soldBy[product.yield_unit]}</p>
        {product.description && <p className="mt-1 text-on-surface-variant">{product.description}</p>}
        <div className="mt-auto pt-3">
          <button
            type="button"
            onClick={onToggle}
            aria-pressed={added}
            className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-4 font-medium transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${
              added ? 'bg-secondary-container text-on-secondary-container' : 'border border-outline text-primary hover:bg-primary/8'
            }`}
          >
            <Icon name={added ? 'check' : 'add'} className="h-5 w-5" />
            {added ? t.catalog.added : t.catalog.add}
            <span className="sr-only">{t.catalog.addFor(product.name)}</span>
          </button>
        </div>
      </div>
    </li>
  )
}

/**
 * Productos de una pyme (T15, ADR-009). El cliente marca los que le interesan y pasa a cotizar con ellos ya elegidos.
 * Sin precios: el precio sale al cotizar (ADR-007). Funciona sin red con lo último guardado.
 */
export default function PortalPyme({ id }: { id: string }) {
  const pymes = useCached<Pyme[]>('portal:pymes', '/portal/pymes')
  const products = useCached<PortalProduct[]>(`portal:products:${id}`, `/portal/products?pyme_id=${encodeURIComponent(id)}`)
  const [picked, setPicked] = useState<string[]>([])
  const pyme = pymes.value?.data.find((p) => p.id === id)
  const list = products.value?.data

  const groups = useMemo(() => {
    const out = new Map<string, PortalProduct[]>()
    for (const p of list ?? []) {
      const key = p.category ?? t.catalog.otherCategory
      out.set(key, [...(out.get(key) ?? []), p])
    }
    // Primero las categorías con más productos; "Otros" al final.
    return [...out.entries()].sort(
      ([a, x], [b, y]) =>
        Number(a === t.catalog.otherCategory) - Number(b === t.catalog.otherCategory) || y.length - x.length,
    )
  }, [list])

  const notFound = products.error?.code === 'pyme_not_available' || (pymes.value && !pyme && !pymes.loading)
  if (notFound) {
    return (
      <Page title={t.catalog.title} onBack={() => navigate('/pymes')}>
        <Alert>{t.catalog.notFound}</Alert>
        <Button variant="secondary" className="mt-4" onClick={() => navigate('/pymes')}>
          {t.catalog.backToList}
        </Button>
      </Page>
    )
  }

  const toggle = (pid: string) => setPicked((cur) => (cur.includes(pid) ? cur.filter((x) => x !== pid) : [...cur, pid]))
  const cached = products.value?.fromCache ? products.value : pymes.value?.fromCache ? pymes.value : null

  return (
    <Page title={pyme?.name ?? t.catalog.title} onBack={() => navigate('/pymes')}>
      {cached && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(cached.savedAt))}</Alert>
        </div>
      )}
      {pyme && (
        <div className="mb-6 flex gap-4">
          <PymeAvatar pyme={pyme} size="lg" />
          <div className="min-w-0">
            {pyme.commune && <p className="text-on-surface-variant">{pyme.commune}</p>}
            {pyme.description && <p className="mt-1 max-w-prose text-on-surface">{pyme.description}</p>}
          </div>
        </div>
      )}
      {products.error && !products.value && <Alert>{products.error.userMessage}</Alert>}
      {products.loading && !products.value ? (
        <Spinner label={t.loading} />
      ) : list && list.length === 0 ? (
        <Alert kind="info">{t.catalog.noProducts}</Alert>
      ) : (
        groups.map(([category, items]) => (
          <section key={category} className="mb-6" aria-labelledby={groups.length > 1 ? `cat-${category}` : undefined}>
            {groups.length > 1 && (
              <h2 id={`cat-${category}`} className="mb-3 text-xl font-medium text-on-surface">
                {category}
              </h2>
            )}
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((p) => (
                <ProductCard key={p.id} product={p} added={picked.includes(p.id)} onToggle={() => toggle(p.id)} />
              ))}
            </ul>
          </section>
        ))
      )}
      {/* Botón fijo sobre la navegación inferior: siempre a mano para pasar a cotizar. */}
      <p className="mt-2 text-on-surface-variant">{t.catalog.pricesAtQuote}</p>
      <div className="sticky bottom-24 z-10 mt-3 lg:bottom-6">
        <Button onClick={() => navigate(quotePath(id, picked))} className="w-full shadow-md sm:w-auto">
          {picked.length ? t.catalog.quoteN(picked.length) : t.catalog.quoteWith}
        </Button>
      </div>
    </Page>
  )
}
