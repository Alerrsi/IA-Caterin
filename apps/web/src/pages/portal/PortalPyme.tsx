import { useMemo, useState } from 'react'
import type { PortalProduct, PortalPyme as Pyme } from '../../api'
import { Coupon, Floater, FoodPanel, Plate, Squiggle } from '../../components/Food'
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
  // Tarjeta del catálogo (T21): el producto como un plato redondo. Celular: fila con el plato a la izquierda. Desde
  // 640 px: el plato arriba, grande.
  return (
    <li className="flex gap-4 p-4 sm:flex-col sm:items-center sm:p-6 sm:text-center">
      <ProductPlate product={product} className="w-24 shrink-0 sm:w-40" />
      <div className="flex min-w-0 flex-1 flex-col sm:w-full">
        <h3 className="text-lg font-bold text-on-surface">{product.name}</h3>
        <p className="num text-sm text-on-surface-variant">{t.catalog.soldBy[product.yield_unit]}</p>
        {product.description && <p className="mt-1 text-on-surface-variant">{product.description}</p>}
        <div className="mt-auto pt-3">
          <button
            type="button"
            onClick={onToggle}
            aria-pressed={added}
            className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-5 font-semibold transition-[background-color,translate] duration-150 ease-out focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 active:translate-y-px motion-reduce:active:translate-y-0 ${
              added
                ? 'bg-accent text-on-accent'
                : 'border border-outline bg-surface-container-lowest text-on-surface hover:bg-surface-container-low'
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

/** El producto como plato redondo: su foto si tiene; si no, el plato dibujado (y lo dice para lectores de pantalla). */
function ProductPlate({ product, className }: { product: PortalProduct; className: string }) {
  return (
    <>
      <Plate src={product.photo_url} className={className} />
      {!product.photo_url && <span className="sr-only">{t.catalog.noPhoto}</span>}
    </>
  )
}

function Recommended({ product, added, onToggle }: { product: PortalProduct; added: boolean; onToggle: () => void }) {
  return (
    <article aria-labelledby="recommended-title">
      <Coupon dark title={t.catalog.recommended} className="w-full max-w-sm">
        <div className="flex items-center gap-4">
          <ProductPlate product={product} className="w-16 shrink-0" />
          <div className="min-w-0 flex-1">
            <h3 id="recommended-title" className="font-bold text-on-panel">
              {product.name}
            </h3>
            <p className="num text-sm text-on-panel-variant">{t.catalog.soldBy[product.yield_unit]}</p>
          </div>
        </div>
        <Button variant="tonal" aria-pressed={added} onClick={onToggle} className="mt-4 w-full">
          <Icon name={added ? 'check' : 'add'} className="h-5 w-5" />
          {added ? t.catalog.added : t.catalog.add}
          <span className="sr-only">{t.catalog.addRecommended(product.name)}</span>
        </Button>
      </Coupon>
    </article>
  )
}

/**
 * Portada de la pyme (T19; rehecha en T21 según la imagen de referencia, ADR-013): a la izquierda, el producto
 * destacado con su nombre en dos pesos, cómo se vende, el botón para cotizarlo y quién lo prepara; a la derecha, el panel
 * oscuro en diagonal con el producto como plato enorme, ingredientes flotando y la tarjeta punteada del recomendado.
 * Sin precios (ADR-009): dice cómo se vende y que el precio sale al cotizar.
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
      className="relative mb-10 overflow-hidden rounded-3xl bg-surface-container-lowest shadow-soft lg:grid lg:min-h-[36rem] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:grid-rows-[1fr_auto]"
    >
      <FoodPanel className="lg:col-start-2 lg:row-span-2 lg:row-start-1">
        <div className="relative flex h-[300px] items-center justify-center pb-8 sm:h-[360px] lg:h-full lg:min-h-[36rem]">
          <Floater kind="basil" className="right-[10%] top-[8%] h-12 w-12 rotate-12 lg:right-[14%] lg:h-16 lg:w-16" />
          <Floater kind="tomato" className="left-[8%] top-[12%] h-10 w-10 lg:left-[4%] lg:top-[20%] lg:h-14 lg:w-14" />
          <Floater kind="lemon" className="bottom-[20%] left-[12%] h-9 w-9 lg:bottom-auto lg:left-[10%] lg:top-[58%] lg:h-12 lg:w-12" />
          <ProductPlate
            product={featured}
            className="w-[210px] sm:w-[260px] lg:absolute lg:left-[26%] lg:top-[38%] lg:w-[min(400px,30vw)] lg:-translate-x-1/2 lg:-translate-y-1/2"
          />
        </div>
      </FoodPanel>

      <div className="relative flex flex-col justify-center px-6 pb-8 pt-2 md:px-10 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:py-12 lg:pl-12">
        <p className="flex items-center gap-3 text-sm font-semibold text-on-surface-variant">
          <Squiggle className="h-5 w-10 shrink-0" />
          {t.catalog.featured}
        </p>
        <h2 id="showcase-title" className="mt-3 text-[2.6rem] leading-[1.05] tracking-tight text-on-surface md:text-6xl md:leading-[1.02]">
          {first && <span className="block font-normal">{first} </span>}
          <span className="block font-extrabold">{rest}</span>
        </h2>
        {blurb && <p className="mt-4 max-w-prose text-lg text-on-surface-variant">{blurb}</p>}

        <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-4">
          <p>
            <span className="num block text-3xl text-on-surface">{t.catalog.soldBy[featured.yield_unit]}</span>
            <span className="text-sm text-on-surface-variant">{t.catalog.priceAtQuote}</span>
          </p>
          <Button icon="quote" onClick={onQuote} className="min-h-14 w-full text-lg sm:w-auto">
            {t.catalog.quoteProduct(featured.name)}
          </Button>
        </div>

        {/* "Lo prepara": el bloque de recomendación de la referencia, con el logo o la inicial de la pyme. */}
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <span className="rounded-full border-2 border-dashed border-outline-variant p-1">
            <PymeAvatar pyme={pyme} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-on-surface-variant">{t.catalog.madeBy}</p>
            <p className="font-bold text-on-surface">{pyme.name}</p>
            {pyme.commune && <p className="text-sm text-on-surface-variant">{pyme.commune}</p>}
          </div>
          <Button variant="ghost" onClick={seeAll} className="-ml-3">
            {t.catalog.seeAll(total)}
            <Icon name="back" className="h-5 w-5 -rotate-90" />
          </Button>
        </div>
      </div>

      {/* El recomendado: sobre el panel oscuro en escritorio (abajo a la derecha); bajo el texto en el celular. */}
      {recommended && (
        <div className="relative z-10 px-6 pb-8 md:px-10 lg:col-start-2 lg:row-start-2 lg:flex lg:justify-end lg:px-10 lg:pb-10">
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
              <h2 id={`cat-${category}`} className="mb-4 text-2xl font-extrabold text-on-surface">
                {category}
              </h2>
            )}
            <Cells className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
      <div className="sticky bottom-28 z-10 mt-3 lg:static">
        <Button icon="quote" onClick={() => navigate(quotePath(id, picked))} className="w-full shadow-soft ring-2 ring-surface-container-lowest sm:w-auto">
          {picked.length ? t.catalog.quoteN(picked.length) : t.catalog.quoteWith}
        </Button>
      </div>
    </Page>
  )
}
