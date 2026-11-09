import { useEffect, useState } from 'react'
import { t } from './i18n'

type Health = 'checking' | 'ok' | 'degraded' | 'down'

export default function App() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    fetch('/api/v1/health/ready')
      .then(async (r) => setHealth(r.ok ? ((await r.json()).status as Health) : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="text-3xl font-bold text-brand">{t.appName}</h1>
      <p className="mt-1 text-stone-700">{t.tagline}</p>
      <p role="status" className="mt-6 rounded-xl bg-white p-4 shadow-sm">
        {t.health[health]}
      </p>
    </main>
  )
}
