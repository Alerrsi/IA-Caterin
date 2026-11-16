import { useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '../auth'
import { t } from '../i18n'
import { navigate } from '../router'
import { useShortcut } from '../shortcuts'
import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { Kbd } from './ui'

interface Dest {
  path: string
  label: string
  icon: IconName
  /** Aparece en la barra inferior del celular (máximo 4; el resto queda en el menú). */
  bar?: boolean
  /** Atajo de teclado de una tecla (T16); se muestra en el cajón de escritorio. */
  shortcut?: string
}

function destinations(role: string | undefined): Dest[] {
  if (role === 'customer') {
    return [
      { path: '/', label: t.nav.myQuotes, icon: 'orders', bar: true },
      { path: '/pymes', label: t.nav.pymes, icon: 'store', bar: true },
      { path: '/cotizar', label: t.nav.newQuote, icon: 'add', bar: true, shortcut: 'C' },
    ]
  }
  const owner = role === 'owner'
  const all: (Dest | false)[] = [
    { path: '/', label: t.nav.home, icon: 'home', bar: true },
    { path: '/cotizar', label: t.nav.quote, icon: 'quote', bar: true, shortcut: 'C' },
    { path: '/pedidos', label: t.nav.orders, icon: 'orders', bar: true },
    { path: '/preguntar', label: t.nav.assistant, icon: 'chat', bar: true },
    { path: '/inventario', label: t.nav.inventory, icon: 'inventory' },
    { path: '/recetas', label: t.nav.recipes, icon: 'restaurant' },
    { path: '/foto', label: t.nav.vision, icon: 'camera' },
    owner && { path: '/tablero', label: t.nav.dashboard, icon: 'trend' },
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
        aria-keyshortcuts={dest.shortcut}
        className={`flex h-14 items-center gap-3 rounded-lg pl-2 pr-4 text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 ${
          active ? 'bg-primary text-on-primary' : 'text-on-surface hover:bg-surface-container'
        }`}
      >
        <span
          className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${active ? 'bg-accent text-on-accent' : 'bg-surface-container text-on-surface'}`}
        >
          <Icon name={dest.icon} className="h-5 w-5" />
        </span>
        <span className="flex-1">{dest.label}</span>
        {dest.shortcut && <Kbd>{dest.shortcut}</Kbd>}
      </a>
    </li>
  )
}

/**
 * Marco de la app (T21, ADR-013: estética de la referencia), adaptable del celular al escritorio:
 * - Desde 1024 px: barra superior limpia con el logo a la izquierda, los destinos principales en píldoras, "Más"
 *   (abre el cajón con todo) y "Salir" en píldora delineada.
 * - Más angosto: barra superior con menú (cajón modal) y una barra inferior flotante oscura con los destinos
 *   principales; el activo lleva el círculo amarillo.
 */
export function AppShell({ path, children }: { path: string; children: ReactNode }) {
  const { user, pyme, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const dests = destinations(user?.role)
  const main = dests.filter((d) => d.bar)
  const more = dests.length > main.length
  const customer = user?.role === 'customer' // trabaja con varias pymes: no se muestra una sola
  const subtitle = customer ? t.portal.portalName : pyme?.name
  useShortcut('c', () => navigate('/cotizar'))

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const logoutButton = (className = '') => (
    <button
      type="button"
      onClick={() => void logout()}
      className={`inline-flex h-12 items-center gap-2 whitespace-nowrap rounded-lg border border-outline px-5 text-base font-semibold text-on-surface transition-colors hover:bg-surface-container focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 ${className}`}
    >
      <Icon name="logout" className="h-5 w-5" />
      {t.home.logout}
    </button>
  )

  return (
    <div className="min-h-dvh">
      {/* Escritorio: barra superior limpia, como la de la referencia. */}
      <header className="sticky top-0 z-20 hidden border-b border-hairline bg-surface-container-lowest/95 backdrop-blur lg:block">
        <div className="mx-auto flex h-20 max-w-7xl items-center gap-4 px-6 xl:gap-6 xl:px-8">
          <a href="#/" className="flex min-w-0 shrink-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40">
            <Logo />
            <span className="hidden max-w-44 truncate text-sm text-on-surface-variant 2xl:inline">{subtitle}</span>
          </a>
          <nav aria-label={t.nav.label} className="flex flex-1 justify-center">
            <ul className="flex items-center gap-1">
              {main.map((d) => {
                const active = isActive(d.path, path)
                return (
                  <li key={d.path}>
                    <a
                      href={`#${d.path}`}
                      aria-current={active ? 'page' : undefined}
                      aria-keyshortcuts={d.shortcut}
                      className={`inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-lg px-4 text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 ${
                        active ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                      }`}
                    >
                      {d.label}
                      {d.shortcut && <Kbd>{d.shortcut}</Kbd>}
                    </a>
                  </li>
                )
              })}
              {more && (
                <li>
                  <button
                    type="button"
                    onClick={() => setOpen(true)}
                    aria-expanded={open}
                    className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-lg px-4 text-base font-semibold text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
                  >
                    {t.nav.more}
                    <Icon name="menu" className="h-5 w-5" />
                  </button>
                </li>
              )}
            </ul>
          </nav>
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden max-w-40 truncate text-sm text-on-surface-variant 2xl:inline">{user?.full_name}</span>
            {logoutButton()}
          </div>
        </div>
      </header>

      {/* Celular y tablet: barra superior */}
      <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-hairline bg-surface-container-lowest/95 px-2 backdrop-blur lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t.nav.open}
          aria-expanded={open}
          className="inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface transition-colors hover:bg-surface-container focus-visible:ring-4 focus-visible:ring-primary/40"
        >
          <Icon name="menu" />
        </button>
        {/* El título de la sección ya está en la pantalla: aquí va la app y la pyme. */}
        <p className="flex min-w-0 flex-1 items-center">
          <Logo size="sm" className="shrink-0" />
          <span className="ml-3 truncate text-sm text-on-surface-variant">{subtitle}</span>
        </p>
      </header>

      {open && (
        <div className="fixed inset-0 z-40">
          <button
            type="button"
            aria-label={t.nav.close}
            className="absolute inset-0 h-full w-full bg-black/40 transition-opacity duration-200 ease-out starting:opacity-0 motion-reduce:transition-none"
            onClick={() => setOpen(false)}
          />
          {/* Entra desde la izquierda con la curva de cajón (300 ms); sin movimiento si se pidió reducirlo. */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t.nav.label}
            className="absolute inset-y-0 left-0 w-80 max-w-[85vw] overscroll-contain rounded-r-2xl bg-surface-container-lowest shadow-soft transition-[translate] duration-300 ease-drawer starting:-translate-x-full motion-reduce:transition-none"
          >
            <div className="flex h-full flex-col px-3 py-5">
              <div className="flex items-start justify-between gap-2 px-3 pb-5">
                <div className="min-w-0">
                  <Logo />
                  <p className="mt-2 truncate text-sm text-on-surface-variant">{subtitle}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label={t.nav.close}
                  className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-container text-on-surface focus-visible:ring-4 focus-visible:ring-primary/40"
                >
                  <Icon name="close" />
                </button>
              </div>
              <nav aria-label={t.nav.label} className="flex-1 overflow-y-auto">
                <ul className="space-y-1">
                  {dests.map((d) => (
                    <DrawerItem key={d.path} dest={d} path={path} onNavigate={() => setOpen(false)} />
                  ))}
                </ul>
              </nav>
              <div className="border-t border-hairline px-2 pt-4">
                <p className="truncate px-1 pb-2 text-sm text-on-surface-variant">{user?.full_name}</p>
                {logoutButton('w-full justify-center')}
              </div>
            </div>
          </div>
        </div>
      )}

      {children}

      {/* Celular y tablet: barra inferior flotante oscura; el destino activo lleva el círculo amarillo. */}
      <nav
        aria-label={t.nav.main}
        className="fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] z-20 rounded-[28px] bg-panel shadow-soft lg:hidden"
      >
        <ul className="mx-auto flex max-w-xl px-1">
          {main.map((d) => {
            const active = isActive(d.path, path)
            return (
              <li key={d.path} className="flex-1">
                <a
                  href={`#${d.path}`}
                  aria-current={active ? 'page' : undefined}
                  className="flex h-[4.5rem] flex-col items-center justify-center gap-1 rounded-[24px] text-xs font-semibold text-on-panel-variant focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-accent"
                >
                  <span
                    className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${active ? 'bg-accent text-on-accent' : ''}`}
                  >
                    <Icon name={d.icon} className="h-5 w-5" />
                  </span>
                  <span className={active ? 'text-on-panel' : ''}>{d.label}</span>
                </a>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
