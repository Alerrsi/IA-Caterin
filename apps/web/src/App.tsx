import { AuthProvider, useAuth } from './auth'
import { OfflineBanner, Spinner } from './components/ui'
import { t } from './i18n'
import Assistant from './pages/Assistant'
import Home from './pages/Home'
import Imports from './pages/Imports'
import IngredientDetail from './pages/IngredientDetail'
import Inventory from './pages/Inventory'
import RecipeDetail from './pages/RecipeDetail'
import Recipes from './pages/Recipes'
import Register from './pages/Register'
import Settings from './pages/Settings'
import Vision from './pages/Vision'
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
  if (status === 'anonymous') return matchPath('/registro', path) ? <Register /> : <Login />

  const quote = matchPath('/cotizaciones/:id', path)
  if (quote) return <QuoteView key={quote.id} id={quote.id} />
  if (matchPath('/cotizar', path)) return <NewQuote />
  if (matchPath('/pedidos', path)) return <Orders />
  if (matchPath('/metricas', path)) return <Metrics />
  if (matchPath('/preguntar', path)) return <Assistant />
  const ingredient = matchPath('/inventario/:id', path)
  if (ingredient) return <IngredientDetail key={ingredient.id} id={ingredient.id} />
  if (matchPath('/inventario', path)) return <Inventory />
  const recipe = matchPath('/recetas/:id', path)
  if (recipe) return <RecipeDetail key={recipe.id} id={recipe.id} />
  if (matchPath('/recetas', path)) return <Recipes />
  if (matchPath('/foto', path)) return <Vision />
  if (matchPath('/ajustes', path)) return <Settings />
  if (matchPath('/importar', path)) return <Imports />
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
