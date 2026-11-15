import { loadAllIngredients, type Ingredient, type OrderOut } from '../api'
import { useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { Cells, Num, Page } from '../components/ui'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'

/**
 * Acceso principal: una celda de la grilla del inicio (T16). La primera ("Cotizar") va destacada con el contenedor
 * primario y ocupa todo el ancho.
 */
function ActionCell({
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
    <li className={featured ? 'sm:col-span-2' : ''}>
      <button
        type="button"
        onClick={onClick}
        className={`flex h-full w-full items-start gap-4 p-5 text-left transition-colors focus-visible:relative focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-primary/30 ${
          featured
            ? 'bg-primary-container text-on-primary-container hover:bg-primary-container/80'
            : 'bg-surface-container-lowest text-on-surface hover:bg-surface-container-low'
        }`}
      >
        <span
          className={`inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${
            featured ? 'bg-primary text-on-primary shadow-key' : 'bg-secondary-container text-on-secondary-container'
          }`}
        >
          <Icon name={icon} />
        </span>
        <span>
          <span className={`block font-medium ${featured ? 'font-display text-xl' : 'text-lg'}`}>{label}</span>
          <span className={`mt-1 block ${featured ? '' : 'text-on-surface-variant'}`}>{hint}</span>
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
    plain: 'text-on-surface hover:bg-on-surface/8',
  }[tone]
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={`flex min-h-12 w-full items-center rounded-lg px-4 text-left text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${styles}`}
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
    <section aria-labelledby="alerts-title" className="rounded-xl border border-hairline bg-surface-container-lowest p-4 md:p-5">
      <h2 id="alerts-title" className="mb-3 font-display text-lg text-on-surface">
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
    <Page title={t.home.hello(user?.full_name.split(' ')[0] ?? '')} description={pyme?.name}>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:order-2">
          <Alerts />
        </div>
        <Cells label={t.nav.label} className="sm:grid-cols-2 lg:order-1 lg:col-span-2">
          <ActionCell featured icon="quote" label={t.home.quote} hint={t.home.quoteHint} onClick={() => navigate('/cotizar')} />
          <ActionCell icon="camera" label={t.home.vision} hint={t.home.visionHint} onClick={() => navigate('/foto')} />
          <ActionCell icon="inventory" label={t.home.inventory} hint={t.home.inventoryHint} onClick={() => navigate('/inventario')} />
          <ActionCell icon="chat" label={t.home.assistant} hint={t.home.assistantHint} onClick={() => navigate('/preguntar')} />
          <ActionCell icon="orders" label={t.home.orders} hint={t.home.ordersHint} onClick={() => navigate('/pedidos')} />
          <ActionCell icon="restaurant" label={t.home.recipes} hint={t.home.recipesHint} onClick={() => navigate('/recetas')} />
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
    </Page>
  )
}
