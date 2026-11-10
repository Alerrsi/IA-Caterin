import { loadAllIngredients, type Ingredient, type OrderOut } from '../api'
import { useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'

/** Acceso principal: tarjeta MD3 con ícono. La primera ("Cotizar") va destacada con el contenedor primario. */
function ActionCard({
  label,
  hint,
  icon,
  onClick,
  featured = false,
}: {
  label: string
  hint: string
  icon: IconName
  onClick: () => void
  featured?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-full w-full items-start gap-4 rounded-xl p-5 text-left transition hover:shadow-md focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${
        featured
          ? 'bg-primary-container text-on-primary-container'
          : 'border border-outline-variant bg-surface-container-lowest text-on-surface'
      }`}
    >
      <span
        className={`inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${
          featured ? 'bg-primary text-on-primary' : 'bg-secondary-container text-on-secondary-container'
        }`}
      >
        <Icon name={icon} />
      </span>
      <span>
        <span className="block text-lg font-medium">{label}</span>
        <span className={`mt-1 block ${featured ? '' : 'text-on-surface-variant'}`}>{hint}</span>
      </span>
    </button>
  )
}

function AlertRow({ text, tone, onClick }: { text: string; tone: 'warning' | 'info' | 'plain'; onClick: () => void }) {
  const styles = {
    warning: 'bg-warning-container text-on-warning-container',
    info: 'bg-info-container text-on-info-container',
    plain: 'text-on-surface hover:bg-on-surface/8',
  }[tone]
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={`flex min-h-12 w-full items-center rounded-lg px-4 text-left text-base font-medium focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${styles}`}
      >
        {tone === 'warning' && '⚠ '}
        {text}
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
    <section aria-labelledby="alerts-title" className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 md:p-5">
      <h2 id="alerts-title" className="mb-3 text-base font-medium text-on-surface-variant">
        {t.home.alertsTitle}
      </h2>
      <ul className="space-y-2">
        {requested !== undefined && requested > 0 && (
          <AlertRow text={t.home.requests(requested)} tone="info" onClick={() => navigate('/pedidos')} />
        )}
        {low !== undefined && (
          <AlertRow
            text={low > 0 ? t.home.lowStock(low) : t.home.noLowStock}
            tone={low > 0 ? 'warning' : 'plain'}
            onClick={() => navigate('/inventario')}
          />
        )}
        {upcoming !== undefined && (
          <AlertRow
            text={upcoming > 0 ? t.home.upcoming(upcoming) : t.home.noUpcoming}
            tone="plain"
            onClick={() => navigate('/pedidos')}
          />
        )}
      </ul>
    </section>
  )
}

export default function Home() {
  const { user, pyme } = useAuth()
  const owner = user?.role === 'owner'
  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-4 md:px-8 md:pt-6 lg:pb-12">
      <p className="text-on-surface-variant">{pyme?.name}</p>
      <h1 className="mb-6 text-3xl font-normal text-on-surface md:text-4xl">
        {t.home.hello(user?.full_name.split(' ')[0] ?? '')}
      </h1>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:order-2">
          <Alerts />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2 lg:order-1">
          <div className="sm:col-span-2">
            <ActionCard featured icon="quote" label={t.home.quote} hint={t.home.quoteHint} onClick={() => navigate('/cotizar')} />
          </div>
          <ActionCard icon="camera" label={t.home.vision} hint={t.home.visionHint} onClick={() => navigate('/foto')} />
          <ActionCard icon="inventory" label={t.home.inventory} hint={t.home.inventoryHint} onClick={() => navigate('/inventario')} />
          <ActionCard icon="chat" label={t.home.assistant} hint={t.home.assistantHint} onClick={() => navigate('/preguntar')} />
          <ActionCard icon="orders" label={t.home.orders} hint={t.home.ordersHint} onClick={() => navigate('/pedidos')} />
          <ActionCard icon="recipes" label={t.home.recipes} hint={t.home.recipesHint} onClick={() => navigate('/recetas')} />
          {owner && (
            <ActionCard icon="upload" label={t.home.imports} hint={t.home.importsHint} onClick={() => navigate('/importar')} />
          )}
          {owner && (
            <ActionCard icon="settings" label={t.home.settings} hint={t.home.settingsHint} onClick={() => navigate('/ajustes')} />
          )}
          {owner && (
            <ActionCard icon="metrics" label={t.home.metrics} hint={t.home.metricsHint} onClick={() => navigate('/metricas')} />
          )}
        </div>
      </div>
    </main>
  )
}
