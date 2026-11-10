import { loadAllIngredients, type Ingredient, type OrderOut } from '../api'
import { useAuth } from '../auth'
import { Button } from '../components/ui'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'

function BigAction({ label, hint, onClick }: { label: string; hint: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full rounded-2xl border-2 border-brand bg-white p-5 text-left shadow-sm hover:bg-orange-50 focus-visible:ring-4 focus-visible:ring-orange-300"
    >
      <span className="block text-xl font-bold text-brand">{label}</span>
      <span className="mt-1 block text-stone-700">{hint}</span>
    </button>
  )
}

function SmallAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button variant="secondary" className="w-full" onClick={onClick}>
      {label}
    </Button>
  )
}

/** Avisos del día desde lo guardado en el teléfono: también se ven sin señal. */
function Alerts() {
  const ingredients = useCached<Ingredient[]>('ingredients', loadAllIngredients)
  const orders = useCached<OrderOut[]>('orders:upcoming', '/orders?upcoming_days=7')
  const low = ingredients.value?.data.filter((i) => i.is_active && i.is_low).length
  const upcoming = orders.value?.data.filter((o) => o.status === 'draft' || o.status === 'confirmed').length
  if (low === undefined && upcoming === undefined) return null
  return (
    <section aria-labelledby="alerts-title" className="mb-6 rounded-2xl bg-white p-4 shadow-sm">
      <h2 id="alerts-title" className="mb-2 text-lg font-bold text-stone-900">
        {t.home.alertsTitle}
      </h2>
      <ul className="space-y-2">
        {low !== undefined && (
          <li>
            <button
              type="button"
              onClick={() => navigate('/inventario')}
              className={`min-h-12 w-full rounded-xl px-3 text-left text-lg font-semibold underline-offset-4 hover:underline focus-visible:ring-4 focus-visible:ring-orange-300 ${low > 0 ? 'bg-amber-50 text-amber-950' : 'text-stone-800'}`}
            >
              {low > 0 ? `⚠ ${t.home.lowStock(low)}` : t.home.noLowStock}
            </button>
          </li>
        )}
        {upcoming !== undefined && (
          <li>
            <button
              type="button"
              onClick={() => navigate('/pedidos')}
              className="min-h-12 w-full rounded-xl px-3 text-left text-lg font-semibold text-stone-800 underline-offset-4 hover:underline focus-visible:ring-4 focus-visible:ring-orange-300"
            >
              {upcoming > 0 ? t.home.upcoming(upcoming) : t.home.noUpcoming}
            </button>
          </li>
        )}
      </ul>
    </section>
  )
}

export default function Home() {
  const { user, pyme, logout } = useAuth()
  const owner = user?.role === 'owner'
  return (
    <main className="mx-auto w-full max-w-xl px-4 pb-16 pt-6">
      <p className="text-stone-700">{pyme?.name}</p>
      <h1 className="mb-6 text-3xl font-bold text-brand">{t.home.hello(user?.full_name.split(' ')[0] ?? '')}</h1>
      <Alerts />
      <div className="space-y-4">
        <BigAction label={t.home.quote} hint={t.home.quoteHint} onClick={() => navigate('/cotizar')} />
        <BigAction label={t.home.vision} hint={t.home.visionHint} onClick={() => navigate('/foto')} />
        <BigAction label={t.home.inventory} hint={t.home.inventoryHint} onClick={() => navigate('/inventario')} />
        <BigAction label={t.home.assistant} hint={t.home.assistantHint} onClick={() => navigate('/preguntar')} />
      </div>
      <h2 className="mb-3 mt-8 text-lg font-bold text-stone-900">{t.home.more}</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <SmallAction label={t.home.orders} onClick={() => navigate('/pedidos')} />
        <SmallAction label={t.home.recipes} onClick={() => navigate('/recetas')} />
        {owner && <SmallAction label={t.home.imports} onClick={() => navigate('/importar')} />}
        {owner && <SmallAction label={t.home.settings} onClick={() => navigate('/ajustes')} />}
        {owner && <SmallAction label={t.home.metrics} onClick={() => navigate('/metricas')} />}
      </div>
      <Button variant="ghost" className="mt-8" onClick={() => logout()}>
        {t.home.logout}
      </Button>
    </main>
  )
}
