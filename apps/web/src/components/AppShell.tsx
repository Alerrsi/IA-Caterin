import { useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '../auth'
import { t } from '../i18n'
import { Icon, type IconName } from './Icon'

interface Dest {
  path: string
  label: string
  icon: IconName
  /** Aparece en la barra inferior del celular (máximo 4; el resto queda en el menú). */
  bar?: boolean
}

function destinations(role: string | undefined): Dest[] {
  if (role === 'customer') {
    return [
      { path: '/', label: t.nav.myQuotes, icon: 'orders', bar: true },
      { path: '/cotizar', label: t.nav.newQuote, icon: 'add', bar: true },
    ]
  }
  const owner = role === 'owner'
  const all: (Dest | false)[] = [
    { path: '/', label: t.nav.home, icon: 'home', bar: true },
    { path: '/cotizar', label: t.nav.quote, icon: 'quote', bar: true },
    { path: '/pedidos', label: t.nav.orders, icon: 'orders', bar: true },
    { path: '/preguntar', label: t.nav.assistant, icon: 'chat', bar: true },
    { path: '/inventario', label: t.nav.inventory, icon: 'inventory' },
    { path: '/recetas', label: t.nav.recipes, icon: 'recipes' },
    { path: '/foto', label: t.nav.vision, icon: 'camera' },
    owner && { path: '/importar', label: t.nav.imports, icon: 'upload' },
    owner && { path: '/metricas', label: t.nav.metrics, icon: 'metrics' },
    owner && { path: '/ajustes', label: t.nav.settings, icon: 'settings' },
  ]
  return all.filter((d): d is Dest => d !== false)
}

function isActive(dest: string, path: string): boolean {
  const clean = path.split('?')[0]
  if (dest === '/') return clean === '/' || clean.startsWith('/solicitudes/') // detalle de una cotización del cliente
  if (dest === '/pedidos' && clean.startsWith('/cotizaciones/')) return true
  return clean === dest || clean.startsWith(`${dest}/`)
}

function DrawerItem({ dest, path, onNavigate }: { dest: Dest; path: string; onNavigate?: () => void }) {
  const active = isActive(dest.path, path)
  return (
    <li>
      <a
        href={`#${dest.path}`}
        onClick={onNavigate}
        aria-current={active ? 'page' : undefined}
        className={`flex h-14 items-center gap-3 rounded-full px-4 text-base font-medium focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${
          active ? 'bg-secondary-container text-on-secondary-container' : 'text-on-surface-variant hover:bg-on-surface/8'
        }`}
      >
        <Icon name={dest.icon} className="h-6 w-6" />
        {dest.label}
      </a>
    </li>
  )
}

/**
 * Marco de la app con Material Design 3, pensado primero para escritorio y adaptable al celular:
 * - Desde 1024 px: cajón de navegación fijo a la izquierda y el contenido al lado.
 * - Más angosto: barra superior con menú (cajón modal) y barra de navegación inferior con los destinos principales.
 */
export function AppShell({ path, children }: { path: string; children: ReactNode }) {
  const { user, pyme, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const dests = destinations(user?.role)
  const customer = user?.role === 'customer' // trabaja con varias pymes: no se muestra una sola

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const drawer = (onNavigate?: () => void) => (
    <div className="flex h-full flex-col px-3 py-4">
      <div className="px-4 pb-4">
        <p className="text-xl font-medium text-on-surface">{t.appName}</p>
        <p className="truncate text-sm text-on-surface-variant">{customer ? t.portal.portalName : pyme?.name}</p>
      </div>
      <nav aria-label={t.nav.label} className="flex-1 overflow-y-auto">
        <ul className="space-y-1">
          {dests.map((d) => (
            <DrawerItem key={d.path} dest={d} path={path} onNavigate={onNavigate} />
          ))}
        </ul>
      </nav>
      <div className="border-t border-outline-variant px-1 pt-3">
        <p className="truncate px-3 text-sm text-on-surface-variant">{user?.full_name}</p>
        <button
          type="button"
          onClick={() => void logout()}
          className="mt-1 flex h-12 w-full items-center gap-3 rounded-full px-3 text-base font-medium text-on-surface-variant hover:bg-on-surface/8 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30"
        >
          <Icon name="logout" className="h-6 w-6" />
          {t.home.logout}
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-dvh lg:pl-72">
      {/* Escritorio: cajón fijo */}
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-outline-variant bg-surface-container-low lg:block">
        {drawer()}
      </aside>

      {/* Celular y tablet: barra superior */}
      <header className="sticky top-0 z-20 flex h-16 items-center gap-2 bg-surface-container px-2 lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t.nav.open}
          aria-expanded={open}
          className="inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface-variant hover:bg-on-surface/8 focus-visible:ring-4 focus-visible:ring-primary/30"
        >
          <Icon name="menu" />
        </button>
        {/* El título de la sección ya está en la pantalla: aquí va la app y la pyme, como en el cajón. */}
        <p className="min-w-0 flex-1 truncate">
          <span className="text-lg text-on-surface">{t.appName}</span>
          <span className="ml-2 text-sm text-on-surface-variant">{customer ? t.portal.portalName : pyme?.name}</span>
        </p>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label={t.nav.close}
            className="absolute inset-0 h-full w-full bg-black/30"
            onClick={() => setOpen(false)}
          />
          <div role="dialog" aria-modal="true" aria-label={t.nav.label} className="absolute inset-y-0 left-0 w-80 max-w-[85vw] rounded-r-2xl bg-surface-container-low shadow-xl">
            {drawer(() => setOpen(false))}
          </div>
        </div>
      )}

      {children}

      {/* Celular y tablet: barra de navegación inferior (MD3 navigation bar) */}
      <nav
        aria-label={t.nav.main}
        className="fixed inset-x-0 bottom-0 z-20 border-t border-outline-variant bg-surface-container pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <ul className="mx-auto flex max-w-xl">
          {dests
            .filter((d) => d.bar)
            .map((d) => {
              const active = isActive(d.path, path)
              return (
                <li key={d.path} className="flex-1">
                  <a
                    href={`#${d.path}`}
                    aria-current={active ? 'page' : undefined}
                    className="flex h-20 flex-col items-center justify-center gap-1 text-xs font-medium text-on-surface-variant focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-primary/30"
                  >
                    <span
                      className={`inline-flex h-8 w-16 items-center justify-center rounded-full ${active ? 'bg-secondary-container text-on-secondary-container' : ''}`}
                    >
                      <Icon name={d.icon} />
                    </span>
                    <span className={active ? 'text-on-surface' : ''}>{d.label}</span>
                  </a>
                </li>
              )
            })}
        </ul>
      </nav>
    </div>
  )
}
