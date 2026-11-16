import { useMemo, useState } from 'react'
import type { PortalProduct, PortalPyme as Pyme } from '../../api'
import { Alert, Button, Cells, Page, Spinner } from '../../components/ui'
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
  // Una celda de la grilla (T16). Celular: fila compacta con miniatura. Desde 640 px: la foto arriba, en un marco
  // punteado como la línea de corte de una comanda.
  return (
    <li className="flex gap-3 p-3 sm:flex-col sm:p-4">
      <div className="shrink-0 rounded-sm border border-dashed border-outline-variant p-1">
        {product.photo_url ? (
          <img
            src={product.photo_url}
            alt=""
            loading="lazy"
            width={800}
            height={600}
            className="h-24 w-24 object-cover sm:aspect-[4/3] sm:h-auto sm:w-full"
          />
        ) : (
          <div className="flex h-24 w-24 items-center justify-center bg-surface-container-high text-on-surface-variant sm:aspect-[4/3] sm:h-auto sm:w-full">
            <Icon name="cloche" className="h-9 w-9 sm:h-12 sm:w-12" />
            <span className="sr-only">{t.catalog.noPhoto}</span>
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col sm:pt-3">
        <h3 className="text-lg font-medium text-on-surface">{product.name}</h3>
        <p className="num text-sm text-on-surface-variant">{t.catalog.soldBy[product.yield_unit]}</p>
        {product.description && <p className="mt-1 text-on-surface-variant">{product.description}</p>}
        <div className="mt-auto pt-3">
          <button
            type="button"
            onClick={onToggle}
            aria-pressed={added}
            className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-4 font-medium transition-[background-color,translate] duration-150 ease-out focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 active:translate-y-px motion-reduce:active:translate-y-0 ${
              added
                ? 'bg-secondary-container text-on-secondary-container'
                : 'border border-outline bg-surface-container-lowest text-on-surface shadow-cap hover:bg-surface-container-low'
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
 * Producto destacado y recomendado (T19, ADR-012), con una regla determinista sobre el orden del catálogo: primero el
 * que tiene foto, luego el que tiene descripción, luego el primero. El recomendado es el siguiente con el mismo criterio.
 */
export function pickShowcase(products: PortalProduct[]): {
  featured: PortalProduct | null
  recommended: PortalProduct | null
} {
  const rank = (p: PortalProduct) => (p.photo_url ? 0 : p.description ? 1 : 2)
  const ordered = products.map((p, i) => ({ p, i })).sort((a, b) => rank(a.p) - rank(b.p) || a.i - b.i)
  return { featured: ordered[0]?.p ?? null, recommended: ordered[1]?.p ?? null }
}

/** "Empanadas de pino" -> ["Empanadas", "de pino"]: el título en dos tonos de la portada. */
export function splitTitle(name: string): [string, string] {
  const words = name.trim().split(/\s+/)
  return words.length < 2 ? ['', name.trim()] : [words[0], words.slice(1).join(' ')]
}

/** Foto del producto, o el vacío del plano (papel cuadriculado y campana) si no tiene. */
function Photo({ product, className }: { product: PortalProduct; className: string }) {
  return product.photo_url ? (
    <img src={product.photo_url} alt="" width={800} height={600} className={`${className} object-cover`} />
  ) : (
    <div
      className={`${className} grid-paper flex items-center justify-center bg-surface-container-lowest text-on-surface-variant`}
    >
      <Icon name="cloche" className="h-1/3 max-h-24 w-1/3 max-w-24 text-outline" />
      <span className="sr-only">{t.catalog.noPhoto}</span>
    </div>
  )
}

/** Marca del plano que "flota" (cuadrado fino o punto cobre). Solo decoración. */
function Mark({ className, dot = false }: { className: string; dot?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`pointer-events-none absolute ${dot ? 'h-2 w-2 rounded-full' : 'h-2.5 w-2.5 border'} ${className}`}
    />
  )
}

function Recommended({ product, added, onToggle }: { product: PortalProduct; added: boolean; onToggle: () => void }) {
  return (
    <article
      aria-labelledby="recommended-title"
      className="w-full max-w-sm rounded-xl border border-dashed border-outline bg-surface-container-lowest p-4"
    >
      <p className="flex items-center gap-2 text-sm font-medium text-on-surface-variant">
        <span aria-hidden="true" className="h-2 w-2 bg-tertiary" />
        {t.catalog.recommended}
      </p>
      <div className="mt-3 flex items-center gap-3 border-t border-dashed border-outline-variant pt-3">
        <div className="shrink-0 rounded-sm border border-dashed border-outline-variant p-0.5">
          <Photo product={product} className="h-16 w-16" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 id="recommended-title" className="font-medium text-on-surface">
            {product.name}
          </h3>
          <p className="num text-sm text-on-surface-variant">{t.catalog.soldBy[product.yield_unit]}</p>
        </div>
      </div>
      <Button variant={added ? 'tonal' : 'secondary'} aria-pressed={added} onClick={onToggle} className="mt-3 w-full">
        <Icon name={added ? 'check' : 'add'} className="h-5 w-5" />
        {added ? t.catalog.added : t.catalog.add}
        <span className="sr-only">{t.catalog.addRecommended(product.name)}</span>
      </Button>
    </article>
  )
}

/**
 * Portada de la pyme (T19, ADR-012): el producto destacado en grande sobre el panel laurel con corte diagonal.
 * Celular: foto arriba, texto y la tarjeta recomendada debajo. Escritorio: texto a la izquierda; foto y tarjeta sobre
 * el panel, a la derecha. Sin precios (ADR-009): dice cómo se vende y que el precio sale al cotizar.
 */
function Showcase({
  pyme,
  featured,
  recommended,
  total,
  picked,
  onToggle,
  onQuote,
}: {
  pyme: Pyme
  featured: PortalProduct
  recommended: PortalProduct | null
  total: number
  picked: string[]
  onToggle: (id: string) => void
  onQuote: () => void
}) {
  const [first, rest] = splitTitle(featured.name)
  const blurb = featured.description ?? pyme.description
  const seeAll = () => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    document.getElementById('catalogo')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }
  return (
    <section
      aria-labelledby="showcase-title"
      className="relative mb-8 flex flex-col overflow-hidden rounded-xl bg-surface-container-lowest shadow-cap lg:grid lg:min-h-[32rem] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:grid-rows-[1fr_auto]"
    >
      {/* Escritorio: el panel laurel cubre la columna derecha con un corte diagonal. */}
      <div
        aria-hidden="true"
        className="hatch absolute inset-y-0 right-0 hidden w-[52%] bg-brand [clip-path:polygon(18%_0,100%_0,100%_100%,0_100%)] lg:block"
      />

      <div className="hatch relative flex items-center justify-center bg-brand px-8 pb-12 pt-6 [clip-path:polygon(0_0,100%_0,100%_86%,0_100%)] lg:col-start-2 lg:row-start-1 lg:bg-transparent lg:px-12 lg:pb-6 lg:pt-12 lg:[background-image:none] lg:[clip-path:none]">
        <Mark className="left-6 top-6 border-on-brand/40" />
        <Mark className="right-8 top-10 bg-tertiary-container" dot />
        <Mark className="bottom-16 left-10 border-on-brand/40 lg:bottom-10" />
        <Mark className="bottom-24 right-6 border-on-brand/40" />
        <div className="w-full max-w-[16rem] -rotate-2 rounded-sm border border-dashed border-on-brand/50 p-1.5 motion-reduce:rotate-0 sm:max-w-sm lg:max-w-md">
          <Photo product={featured} className="aspect-[4/3] w-full" />
        </div>
      </div>

      <div className="relative flex flex-col justify-center px-5 pb-6 pt-2 md:px-8 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:px-10 lg:py-12">
        <Mark className="right-6 top-2 border-outline-variant lg:right-10 lg:top-10" />
        <Mark className="right-14 top-8 bg-tertiary lg:top-16" dot />
        <p className="flex items-center gap-2 text-sm font-medium text-on-surface-variant">
          <span aria-hidden="true" className="h-px w-6 bg-outline" />
          {t.catalog.featured}
        </p>
        <h2
          id="showcase-title"
          className="mt-3 font-display text-[2.5rem] leading-[1.08] tracking-tight text-on-surface md:text-5xl md:leading-[1.05] lg:text-[3.5rem]"
        >
          {first && <span className="block text-on-surface-variant">{first} </span>}
          <span className="block">{rest}</span>
        </h2>
        {blurb && <p className="mt-4 max-w-prose text-on-surface-variant">{blurb}</p>}

        <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-4">
          <p>
            <span className="num block text-2xl text-on-surface">{t.catalog.soldBy[featured.yield_unit]}</span>
            <span className="text-sm text-on-surface-variant">{t.catalog.priceAtQuote}</span>
          </p>
          <Button onClick={onQuote} className="w-full sm:w-auto">
            <Icon name="quote" className="h-5 w-5" />
            {t.catalog.quoteProduct(featured.name)}
          </Button>
        </div>

        <div className="mt-8 border-t border-dashed border-outline-variant pt-5">
          <div className="flex items-center gap-3">
            <PymeAvatar pyme={pyme} />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-on-surface-variant">{t.catalog.madeBy}</p>
              <p className="font-medium text-on-surface">{pyme.name}</p>
              {pyme.commune && <p className="text-sm text-on-surface-variant">{pyme.commune}</p>}
            </div>
          </div>
          <Button variant="ghost" onClick={seeAll} className="-ml-5 mt-2">
            {t.catalog.seeAll(total)}
            <Icon name="back" className="h-5 w-5 -rotate-90" />
          </Button>
        </div>
      </div>

      {recommended && (
        <div className="relative flex justify-center px-5 pb-5 md:px-8 lg:col-start-2 lg:row-start-2 lg:px-12 lg:pb-10">
          <Recommended
            product={recommended}
            added={picked.includes(recommended.id)}
            onToggle={() => onToggle(recommended.id)}
          />
        </div>
      )}
    </section>
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
  const { featured, recommended } = pickShowcase(groups.flatMap(([, items]) => items))
  const cached = products.value?.fromCache ? products.value : pymes.value?.fromCache ? pymes.value : null

  return (
    <Page title={pyme?.name ?? t.catalog.title} onBack={() => navigate('/pymes')}>
      {cached && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(cached.savedAt))}</Alert>
        </div>
      )}
      {pyme && featured && (
        <Showcase
          pyme={pyme}
          featured={featured}
          recommended={recommended}
          total={list?.length ?? 0}
          picked={picked}
          onToggle={toggle}
          onQuote={() => navigate(quotePath(id, [featured.id, ...picked.filter((x) => x !== featured.id)]))}
        />
      )}
      {pyme && !featured && (
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
        <div id="catalogo" className="scroll-mt-20">
          {groups.map(([category, items]) => (
          <section key={category} className="mb-6" aria-labelledby={groups.length > 1 ? `cat-${category}` : undefined}>
            {groups.length > 1 && (
              <h2 id={`cat-${category}`} className="mb-3 font-display text-xl text-on-surface">
                {category}
              </h2>
            )}
            <Cells className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((p) => (
                <ProductCard key={p.id} product={p} added={picked.includes(p.id)} onToggle={() => toggle(p.id)} />
              ))}
            </Cells>
          </section>
          ))}
        </div>
      )}
      {/* Botón fijo sobre la navegación inferior: siempre a mano para pasar a cotizar. */}
      <p className="mt-2 text-on-surface-variant">{t.catalog.pricesAtQuote}</p>
      <div className="sticky bottom-24 z-10 mt-3 lg:bottom-6">
        <Button onClick={() => navigate(quotePath(id, picked))} className="w-full sm:w-auto">
          {picked.length ? t.catalog.quoteN(picked.length) : t.catalog.quoteWith}
        </Button>
      </div>
    </Page>
  )
}
