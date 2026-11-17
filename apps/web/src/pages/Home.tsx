import { loadAllIngredients, type Ingredient, type OrderOut } from '../api'
import { useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { Coupon, Floater, FoodPanel, Plate, Squiggle } from '../components/Food'
import { Button, Cells, IconDot, Num } from '../components/ui'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { useRecent } from '../recent'
import { navigate } from '../router'

/** Acceso: tarjeta blanca con el ícono en un círculo amarillo (T21, ADR-013). */
function ActionCell({ label, hint, icon, onClick }: { label: string; hint: string; icon: IconName; onClick: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="flex h-full w-full items-start gap-4 p-5 text-left text-on-surface transition-colors hover:bg-accent-soft focus-visible:relative focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-primary/40"
      >
        <IconDot name={icon} className="h-12 w-12" />
        <span>
          <span className="block text-lg font-bold">{label}</span>
          <span className="mt-1 block text-on-surface-variant">{hint}</span>
        </span>
      </button>
    </li>
  )
}

/** Si el texto parte con una cifra ("5 solicitudes…"), la muestra como cifra de comanda. */
function WithCount({ text }: { text: string }) {
  const m = text.match(/^(\d+)(.*)$/s)
  if (!m) return <>{text}</>
  return (
    <>
      <Num>{m[1]}</Num>
      {m[2]}
    </>
  )
}

function AlertRow({ text, tone, onClick }: { text: string; tone: 'warning' | 'info' | 'plain'; onClick: () => void }) {
  const styles = {
    warning: 'bg-warning-container text-on-warning-container',
    info: 'bg-info-container text-on-info-container',
    plain: 'bg-surface-container text-on-surface hover:bg-surface-container-high',
  }[tone]
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={`flex min-h-12 w-full items-center rounded-lg px-5 text-left text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${styles}`}
      >
        <span>
          {tone === 'warning' && '⚠ '}
          <WithCount text={text} />
        </span>
      </button>
    </li>
  )
}

/** Avisos del día desde lo guardado en el teléfono: también se ven sin señal. */
function Alerts() {
  const ingredients = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const orders = useCached<OrderOut[]>('orders:upcoming', '/orders?upcoming_days=7')
  const requested = useCached<OrderOut[]>('orders:requested', '/orders?status=requested').value?.data.length
  const low = ingredients.value?.data.filter((i) => i.is_active && i.is_low).length
  const upcoming = orders.value?.data.filter((o) => o.status === 'draft' || o.status === 'confirmed').length
  if (low === undefined && upcoming === undefined) return null
  return (
    <section aria-labelledby="alerts-title">
      <Coupon title={<span id="alerts-title">{t.home.alertsTitle}</span>} className="shadow-cap">
      <ul className="space-y-2">
        {requested !== undefined && requested > 0 && (
          <AlertRow text={t.home.requests(requested)} tone="info" onClick={() => navigate('/pedidos?estado=requested')} />
        )}
        {low !== undefined && (
          <AlertRow
            text={low > 0 ? t.home.lowStock(low) : t.home.noLowStock}
            tone={low > 0 ? 'warning' : 'plain'}
            onClick={() => navigate(low > 0 ? '/inventario?bajo=1' : '/inventario')}
          />
        )}
        {upcoming !== undefined && (
          <AlertRow
            text={upcoming > 0 ? t.home.upcoming(upcoming) : t.home.noUpcoming}
            tone="plain"
            onClick={() => navigate(upcoming > 0 ? '/pedidos?proximos=7' : '/pedidos')}
          />
        )}
      </ul>
      </Coupon>
    </section>
  )
}

/**
 * Portada del inicio (T21): saludo grande en dos pesos, la acción principal en píldora con el ícono en un círculo
 * amarillo y, al lado, el panel oscuro con un plato enorme e ingredientes flotando, como la imagen de referencia.
 */
function Hero({ name, pymeName }: { name: string; pymeName?: string }) {
  return (
    <section className="relative overflow-hidden rounded-3xl bg-surface-container-lowest shadow-soft lg:grid lg:min-h-[440px] lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
      <FoodPanel className="h-[250px] sm:h-[300px] lg:order-2 lg:h-auto">
        <div className="relative h-[250px] sm:h-[300px] lg:h-full lg:min-h-[440px]">
          <Floater kind="basil" className="right-[12%] top-[10%] h-12 w-12 rotate-12 lg:h-16 lg:w-16" />
          <Floater kind="tomato" className="left-[10%] top-[14%] h-10 w-10 lg:left-[2%] lg:top-[16%] lg:h-14 lg:w-14" />
          <Plate className="absolute left-1/2 top-[48%] w-[190px] -translate-x-1/2 -translate-y-1/2 sm:w-[230px] lg:left-[38%] lg:top-1/2 lg:w-[340px]" />
          <Floater kind="lemon" className="bottom-[18%] right-[14%] h-10 w-10 lg:bottom-[14%] lg:h-12 lg:w-12" />
        </div>
      </FoodPanel>
      <div className="relative z-10 p-6 md:p-10 lg:order-1 lg:flex lg:flex-col lg:justify-center lg:py-12 lg:pl-12">
        {pymeName && (
          <p className="flex items-center gap-3 text-on-surface-variant">
            <Squiggle className="h-5 w-10 shrink-0" />
            <span className="truncate">{pymeName}</span>
          </p>
        )}
        <h1 className="mt-3 text-[2.3rem] leading-[2.7rem] text-on-surface md:text-6xl md:leading-[4.1rem]">
          <span className="block font-normal">{t.home.hello(name)}</span>
          {t.home.heroBold}
        </h1>
        <p className="mt-3 max-w-md text-lg text-on-surface-variant">{t.home.quoteHint}</p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <Button icon="quote" onClick={() => navigate('/cotizar')} className="min-h-14 text-lg">
            {t.home.quote}
          </Button>
          <Button variant="secondary" onClick={() => navigate('/foto')} className="min-h-14">
            {t.home.vision}
          </Button>
        </div>
      </div>
    </section>
  )
}

/** Acciones rápidas (T22): lo que más se hace, a un toque y con botones grandes. */
function QuickActions() {
  const actions: { label: string; icon: IconName; path: string }[] = [
    { label: t.home.quote, icon: 'quote', path: '/cotizar' },
    { label: t.home.vision, icon: 'camera', path: '/foto' },
    { label: t.home.adjust, icon: 'inventory', path: '/inventario?ajustar=1' },
    { label: t.home.assistant, icon: 'chat', path: '/preguntar' },
  ]
  return (
    <section aria-labelledby="quick-title">
      <h2 id="quick-title" className="mb-3 text-xl font-extrabold text-on-surface">
        {t.home.quickTitle}
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {actions.map((a) => (
          <li key={a.path}>
            <a
              href={`#${a.path}`}
              className="flex min-h-24 flex-col items-start justify-between gap-3 rounded-3xl bg-surface-container-lowest p-4 text-base font-bold text-on-surface shadow-cap transition-colors hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
            >
              <IconDot name={a.icon} className="h-11 w-11" />
              {a.label}
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** "Seguir donde quedaste" (T22): lo último que se abrió en este teléfono. No aparece si no hay nada. */
function Recent({ userId }: { userId?: string }) {
  const items = useRecent(userId)
  if (items.length === 0) return null
  return (
    <section aria-labelledby="recent-title">
      <h2 id="recent-title" className="mb-3 text-xl font-extrabold text-on-surface">
        {t.home.recentTitle}
      </h2>
      <ul className="grid gap-3 sm:grid-cols-3">
        {items.map((i) => (
          <li key={i.path}>
            <a
              href={`#${i.path}`}
              className="flex min-h-16 items-center gap-3 rounded-3xl bg-surface-container-lowest px-4 py-3 shadow-cap transition-colors hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-on-surface-variant">{t.home.recentKinds[i.kind]}</span>
                <span className="block truncate font-bold text-on-surface">{i.label}</span>
              </span>
              <Icon name="back" className="h-5 w-5 shrink-0 rotate-180 text-on-surface-variant" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function Home() {
  const { user, pyme } = useAuth()
  const owner = user?.role === 'owner'
  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-5 md:px-8 md:pt-8 lg:pb-16">
      <Hero name={user?.full_name.split(' ')[0] ?? ''} pymeName={pyme?.name} />
      <div className="mt-6 space-y-6">
        <QuickActions />
        <Recent userId={user?.id} />
      </div>
      <h2 className="mb-3 mt-8 text-xl font-extrabold text-on-surface">{t.home.allTitle}</h2>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:order-2">
          <Alerts />
        </div>
        <Cells label={t.nav.label} className="sm:grid-cols-2 lg:order-1 lg:col-span-2">
          <ActionCell icon="inventory" label={t.home.inventory} hint={t.home.inventoryHint} onClick={() => navigate('/inventario')} />
          <ActionCell icon="chat" label={t.home.assistant} hint={t.home.assistantHint} onClick={() => navigate('/preguntar')} />
          <ActionCell icon="orders" label={t.home.orders} hint={t.home.ordersHint} onClick={() => navigate('/pedidos')} />
          <ActionCell icon="restaurant" label={t.home.recipes} hint={t.home.recipesHint} onClick={() => navigate('/recetas')} />
          {owner && (
            <ActionCell icon="trend" label={t.home.dashboard} hint={t.home.dashboardHint} onClick={() => navigate('/tablero')} />
          )}
          {owner && (
            <ActionCell icon="upload" label={t.home.imports} hint={t.home.importsHint} onClick={() => navigate('/importar')} />
          )}
          {owner && (
            <ActionCell icon="settings" label={t.home.settings} hint={t.home.settingsHint} onClick={() => navigate('/ajustes')} />
          )}
          {owner && (
            <ActionCell icon="metrics" label={t.home.metrics} hint={t.home.metricsHint} onClick={() => navigate('/metricas')} />
          )}
        </Cells>
      </div>
    </main>
  )
}
