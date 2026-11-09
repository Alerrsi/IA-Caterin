import { AuthProvider, useAuth } from './auth'
import { OfflineBanner, Spinner } from './components/ui'
import { t } from './i18n'
import Home from './pages/Home'
import Login from './pages/Login'
import Metrics from './pages/Metrics'
import NewQuote from './pages/NewQuote'
import Orders from './pages/Orders'
import QuoteView from './pages/QuoteView'
import { matchPath, useHashPath } from './router'

function Routes() {
  const { status } = useAuth()
  const path = useHashPath()

  if (status === 'loading') {
    return (
      <main className="mx-auto max-w-md p-6">
        <Spinner label={t.loading} />
      </main>
    )
  }
  if (status === 'anonymous') return <Login />

  const quote = matchPath('/cotizaciones/:id', path)
  if (quote) return <QuoteView key={quote.id} id={quote.id} />
  if (matchPath('/cotizar', path)) return <NewQuote />
  if (matchPath('/pedidos', path)) return <Orders />
  if (matchPath('/metricas', path)) return <Metrics />
  return <Home />
}

export default function App() {
  return (
    <AuthProvider>
      <OfflineBanner />
      <Routes />
    </AuthProvider>
  )
}
