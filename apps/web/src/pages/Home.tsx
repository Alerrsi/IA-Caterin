import { useAuth } from '../auth'
import { Button } from '../components/ui'
import { t } from '../i18n'
import { navigate } from '../router'

function BigAction({ label, hint, onClick, disabled }: { label: string; hint: string; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="block w-full rounded-2xl border-2 border-brand bg-white p-5 text-left shadow-sm hover:bg-orange-50 focus-visible:ring-4 focus-visible:ring-orange-300 disabled:border-stone-300 disabled:bg-stone-100 disabled:shadow-none"
    >
      <span className={`block text-xl font-bold ${disabled ? 'text-stone-600' : 'text-brand'}`}>{label}</span>
      <span className="mt-1 block text-stone-700">{hint}</span>
    </button>
  )
}

export default function Home() {
  const { user, pyme, logout } = useAuth()
  return (
    <main className="mx-auto w-full max-w-xl px-4 pb-16 pt-6">
      <p className="text-stone-700">{pyme?.name}</p>
      <h1 className="mb-6 text-3xl font-bold text-brand">{t.home.hello(user?.full_name.split(' ')[0] ?? '')}</h1>
      <div className="space-y-4">
        <BigAction label={t.home.quote} hint={t.home.quoteHint} onClick={() => navigate('/cotizar')} />
        <BigAction label={t.home.orders} hint={t.home.ordersHint} onClick={() => navigate('/pedidos')} />
        <BigAction label={t.home.vision} hint={t.home.soon} disabled />
        <BigAction label={t.home.assistant} hint={t.home.soon} disabled />
      </div>
      <Button variant="ghost" className="mt-8" onClick={() => logout()}>
        {t.home.logout}
      </Button>
    </main>
  )
}
