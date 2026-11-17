import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '../auth'
import { t } from '../i18n'
import { navigate } from '../router'
import { useShortcut } from '../shortcuts'
import { Dialog } from './Dialog'
import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { QuickFind } from './QuickFind'
import { Kbd } from './ui'

type Group = 'main' | 'sales' | 'kitchen' | 'admin'

interface Dest {
  path: string
  label: string
  /** Etiqueta corta para la barra inferior del celular. */
  short?: string
  icon: IconName
  group: Group
  /** Va en la barra inferior del celular (4 + "Más"). */
  bar?: boolean
  /** Va en la barra superior del escritorio (además de los de la barra inferior). */
  desk?: boolean
  /** Atajo de teclado de una tecla; se muestra en "Más" y en la ayuda (T16, T22). */
  shortcut?: string
}

/**
 * Destinos por rol (T22): lo de todos los días a un toque (barra inferior) y todo lo demás a dos ("Más", agrupado en
 * Ventas, Cocina y Administración). El cliente del portal tiene solo 3 destinos: todos van en la barra.
 */
export function destinations(role: string | undefined): Dest[] {
  if (role === 'customer') {
    return [
      { path: '/', label: t.nav.myQuotes, icon: 'orders', group: 'main', bar: true },
      { path: '/pymes', label: t.nav.pymes, icon: 'store', group: 'main', bar: true },
      { path: '/cotizar', label: t.nav.newQuote, icon: 'add', group: 'main', bar: true, shortcut: 'C' },
    ]
  }
  const owner = role === 'owner'
  const all: (Dest | false)[] = [
    { path: '/', label: t.nav.home, icon: 'home', group: 'main', bar: true },
    { path: '/cotizar', label: t.nav.quote, icon: 'quote', group: 'main', bar: true, shortcut: 'C' },
    { path: '/foto', label: t.nav.vision, short: t.nav.visionShort, icon: 'camera', group: 'main', bar: true, shortcut: 'F' },
    { path: '/inventario', label: t.nav.inventory, icon: 'inventory', group: 'main', bar: true, shortcut: 'I' },
    { path: '/pedidos', label: t.nav.orders, icon: 'orders', group: 'sales', desk: true, shortcut: 'P' },
    { path: '/preguntar', label: t.nav.assistant, icon: 'chat', group: 'sales' },
    owner && { path: '/tablero', label: t.nav.dashboard, icon: 'trend', group: 'sales' },
    { path: '/recetas', label: t.nav.recipes, icon: 'restaurant', group: 'kitchen' },
    { path: '/inventario/productos', label: t.nav.products, icon: 'cloche', group: 'kitchen' },
    owner && { path: '/importar', label: t.nav.imports, icon: 'upload', group: 'admin' },
    owner && { path: '/metricas', label: t.nav.metrics, icon: 'metrics', group: 'admin' },
    owner && { path: '/ajustes', label: t.nav.settings, icon: 'settings', group: 'admin' },
  ]
  return all.filter((d): d is Dest => d !== false)
}

export function isActive(dest: string, path: string): boolean {
  const clean = path.split('?')[0]
  if (dest === '/') return clean === '/' || clean.startsWith('/solicitudes/') // detalle de una cotización del cliente
  if (dest === '/pedidos' && clean.startsWith('/cotizaciones/')) return true
  if (dest === '/inventario' && clean === '/inventario/productos') return false
  return clean === dest || clean.startsWith(`${dest}/`)
}

/** Hoja "Más" (T22): todo lo que no está en la barra, agrupado y con botones grandes. Foco atrapado; Esc cierra. */
function MoreSheet({
  dests,
  path,
  onClose,
  footer,
}: {
  dests: Dest[]
  path: string
  onClose: () => void
  footer: ReactNode
}) {
  // Lo de todos los días ya está en la barra: la hoja muestra solo el resto (en el cliente, sus 3 destinos).
  const groups: Group[] = dests.some((d) => d.group !== 'main') ? ['sales', 'kitchen', 'admin'] : ['main']
  return (
    <Dialog label={t.nav.moreTitle} onClose={onClose}>
      <div className="flex items-center justify-between gap-2 px-5 pb-2 pt-4">
        <h2 className="text-2xl font-extrabold text-on-surface">{t.nav.moreTitle}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={t.nav.close}
          className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-surface-container text-on-surface focus-visible:ring-4 focus-visible:ring-primary/40"
        >
          <Icon name="close" />
        </button>
      </div>
      <nav aria-label={t.nav.label} className="overflow-y-auto overscroll-contain px-4 pb-2">
        {groups.map((g) => {
          const items = dests.filter((d) => d.group === g)
          if (items.length === 0) return null
          return (
            <section key={g} aria-labelledby={`more-${g}`} className="pt-3">
              <h3 id={`more-${g}`} className="px-1 pb-2 text-sm font-semibold text-on-surface-variant">
                {t.nav.groups[g]}
              </h3>
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {items.map((d) => {
                  const active = isActive(d.path, path)
                  return (
                    <li key={d.path}>
                      <a
                        href={`#${d.path}`}
                        onClick={onClose}
                        aria-current={active ? 'page' : undefined}
                        aria-keyshortcuts={d.shortcut}
                        className={`flex min-h-14 items-center gap-3 rounded-2xl py-2 pl-2 pr-3 text-base font-semibold leading-tight transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 ${
                          active ? 'bg-primary text-on-primary' : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
                        }`}
                      >
                        <span
                          className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${active ? 'bg-accent text-on-accent' : 'bg-surface-container-lowest'}`}
                        >
                          <Icon name={d.icon} className="h-5 w-5" />
                        </span>
                        <span className="min-w-0 flex-1">{d.label}</span>
                        {d.shortcut && <Kbd>{d.shortcut}</Kbd>}
                      </a>
                    </li>
                  )
                })}
              </ul>
            </section>
          )
        })}
      </nav>
      <div className="mt-2 border-t border-hairline px-5 pt-3">{footer}</div>
    </Dialog>
  )
}

/** Ayuda de atajos de teclado (tecla "?"). */
function ShortcutsHelp({ customer, onClose }: { customer: boolean; onClose: () => void }) {
  const rows: [string, string][] = [
    ['/', t.keys.findAlt],
    ['C', t.keys.quote],
    ...(customer
      ? []
      : ([
          ['F', t.keys.vision],
          ['I', t.keys.inventory],
          ['P', t.keys.orders],
        ] as [string, string][])),
    ['?', t.keys.help],
  ]
  return (
    <Dialog label={t.keys.title} onClose={onClose}>
      <div className="px-5 pb-2 pt-4">
        <h2 className="text-2xl font-extrabold text-on-surface">{t.keys.title}</h2>
        <p className="mt-1 text-on-surface-variant">{t.keys.intro}</p>
        <dl className="mt-4 divide-y divide-hairline">
          {rows.map(([key, label]) => (
            <div key={key} className="flex min-h-12 items-center justify-between gap-4">
              <dt className="text-on-surface">{label}</dt>
              <dd>
                <kbd className="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-outline px-2 font-semibold">
                  {key}
                </kbd>
              </dd>
            </div>
          ))}
        </dl>
        <button
          type="button"
          onClick={onClose}
          className="mt-4 inline-flex min-h-12 w-full items-center justify-center rounded-full bg-primary px-5 font-semibold text-on-primary focus-visible:ring-4 focus-visible:ring-primary/40"
        >
          {t.keys.close}
        </button>
      </div>
    </Dialog>
  )
}

/**
 * Al cambiar de pantalla (no de filtro): arriba de la página, foco al título y anuncio para el lector de pantalla (T22).
 */
function useScreenChange(path: string): string {
  const [announce, setAnnounce] = useState('')
  const screen = path.split('?')[0]
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    const timer = window.setTimeout(() => {
      const h1 = document.querySelector<HTMLElement>('#contenido h1')
      if (!navigator.userAgent.includes('jsdom')) window.scrollTo({ top: 0 })
      if (!h1) return
      if (!h1.hasAttribute('tabindex')) h1.setAttribute('tabindex', '-1')
      // Si la pantalla ya puso el foco en un campo (p. ej. "Ajustar stock" enfoca el buscador), se respeta.
      const current = document.activeElement
      const inField = current instanceof HTMLElement && current !== h1 && ['INPUT', 'TEXTAREA', 'SELECT'].includes(current.tagName)
      if (!inField && !document.querySelector('[aria-modal="true"]')) h1.focus({ preventScroll: true })
      setAnnounce(t.nav.screen((h1.textContent ?? '').trim()))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [screen])
  return announce
}

/**
 * Marco de la app (T21 estética de la referencia; T22 acceso rápido):
 * - Celular: barra superior con el logo y el buscador; barra inferior flotante oscura con 4 destinos + "Más".
 * - Escritorio (≥ 1024 px): barra superior con los destinos principales en píldoras, "Más", el buscador y "Salir".
 * - En todas: "Saltar al contenido", buscador con Ctrl/⌘ K y "/", atajos C, F, I, P y ayuda con "?".
 */
export function AppShell({ path, children }: { path: string; children: ReactNode }) {
  const { user, pyme, logout } = useAuth()
  const [more, setMore] = useState(false)
  const [finding, setFinding] = useState(false)
  const [help, setHelp] = useState(false)
  const role = user?.role
  const customer = role === 'customer' // trabaja con varias pymes: no se muestra una sola
  const dests = destinations(role)
  const bar = dests.filter((d) => d.bar)
  const desk = dests.filter((d) => d.bar || d.desk)
  const deskMore = dests.length > desk.length
  const screen = path.split('?')[0]
  // Pantallas con su propio buscador: ahí "/" enfoca ese buscador (T16) y no abre el global.
  const localSearch = screen === '/inventario' || (customer && screen === '/pymes')
  const subtitle = customer ? t.portal.portalName : pyme?.name
  const announce = useScreenChange(path)
  const anyOpen = more || finding || help

  useShortcut('c', () => navigate('/cotizar'), !anyOpen)
  useShortcut('f', () => navigate('/foto'), !customer && !anyOpen)
  useShortcut('i', () => navigate('/inventario'), !customer && !anyOpen)
  useShortcut('p', () => navigate('/pedidos'), !customer && !anyOpen)
  useShortcut('?', () => setHelp(true), !anyOpen)
  // "/" abre el buscador global, salvo en pantallas con su propio buscador (Inventario, directorio de pymes).
  useShortcut('/', () => setFinding(true), !anyOpen && !localSearch)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setMore(false)
        setHelp(false)
        setFinding(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const logoutButton = (className = '', compact = false) => (
    <button
      type="button"
      onClick={() => void logout()}
      aria-label={compact ? t.home.logout : undefined}
      className={`inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-lg border border-outline px-4 text-base font-semibold text-on-surface transition-colors hover:bg-surface-container focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 ${className}`}
    >
      <Icon name="logout" className="h-5 w-5" />
      <span className={compact ? 'sr-only xl:not-sr-only' : ''}>{t.home.logout}</span>
    </button>
  )

  const findButton = (wide: boolean) => (
    <button
      type="button"
      onClick={() => setFinding(true)}
      aria-label={wide ? undefined : t.find.open}
      aria-keyshortcuts="Control+K Meta+K /"
      aria-haspopup="dialog"
      className={
        wide
          ? 'inline-flex h-12 items-center gap-2 whitespace-nowrap rounded-full bg-surface-container px-4 text-base text-on-surface-variant transition-colors hover:bg-surface-container-high focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40'
          : 'inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-container text-on-surface transition-colors hover:bg-surface-container-high focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40'
      }
    >
      <Icon name="search" className="h-5 w-5" />
      {wide && (
        <>
          <span className="hidden xl:inline">{t.find.open}</span>
          <Kbd>/</Kbd>
        </>
      )}
    </button>
  )

  return (
    <div className="min-h-dvh">
      {/* Primer elemento con Tab: salta la navegación (es un botón: el router usa el hash). */}
      <button
        type="button"
        onClick={() => document.getElementById('contenido')?.focus()}
        className="sr-only z-50 rounded-full bg-primary px-5 py-3 font-semibold text-on-primary focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:outline-none focus:ring-4 focus:ring-accent"
      >
        {t.nav.skip}
      </button>
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </p>

      {/* Escritorio: barra superior limpia, como la de la referencia. */}
      <header className="sticky top-0 z-20 hidden border-b border-hairline bg-surface-container-lowest/95 backdrop-blur lg:block">
        <div className="mx-auto flex h-20 max-w-7xl items-center gap-3 px-6 xl:gap-5 xl:px-8">
          <a href="#/" className="flex min-w-0 shrink-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40">
            <Logo />
            <span className="sr-only">{subtitle}</span>
          </a>
          <nav aria-label={t.nav.label} className="flex flex-1 justify-center">
            <ul className="flex items-center gap-1">
              {desk.map((d) => {
                const active = isActive(d.path, path)
                return (
                  <li key={d.path}>
                    <a
                      href={`#${d.path}`}
                      aria-current={active ? 'page' : undefined}
                      aria-keyshortcuts={d.shortcut}
                      className={`inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-lg px-3 text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 xl:px-4 ${
                        active ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                      }`}
                    >
                      {d.label}
                      {d.shortcut && <Kbd>{d.shortcut}</Kbd>}
                    </a>
                  </li>
                )
              })}
              {deskMore && (
                <li>
                  <button
                    type="button"
                    onClick={() => setMore(true)}
                    aria-haspopup="dialog"
                    aria-expanded={more}
                    className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-lg px-3 text-base font-semibold text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 xl:px-4"
                  >
                    {t.nav.more}
                    <Icon name="menu" className="h-5 w-5" />
                  </button>
                </li>
              )}
            </ul>
          </nav>
          <div className="flex shrink-0 items-center gap-2">
            {findButton(true)}
            <button
              type="button"
              onClick={() => setHelp(true)}
              aria-label={t.keys.open}
              aria-keyshortcuts="?"
              className="inline-flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-on-surface-variant hover:bg-surface-container focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
            >
              ?
            </button>
            {logoutButton('', true)}
          </div>
        </div>
      </header>

      {/* Celular y tablet: barra superior con el logo y el buscador. */}
      <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-hairline bg-surface-container-lowest/95 px-3 backdrop-blur lg:hidden">
        {/* El título de la sección ya está en la pantalla: aquí va la app y la pyme. */}
        <a href="#/" className="flex min-w-0 flex-1 items-center rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40">
          <Logo size="sm" className="shrink-0" />
          <span className="ml-3 truncate text-sm text-on-surface-variant">{subtitle}</span>
        </a>
        {findButton(false)}
      </header>

      <div id="contenido" tabIndex={-1} className="outline-none">
        {children}
      </div>

      {/* Celular y tablet: barra inferior flotante oscura; el destino activo lleva el círculo amarillo. */}
      <nav
        aria-label={t.nav.main}
        className="fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] z-20 rounded-[28px] bg-panel shadow-soft lg:hidden"
      >
        <ul className="mx-auto flex max-w-xl px-1">
          {bar.map((d) => {
            const active = isActive(d.path, path)
            return (
              <li key={d.path} className="min-w-0 flex-1">
                <a
                  href={`#${d.path}`}
                  aria-current={active ? 'page' : undefined}
                  aria-label={d.short ? d.label : undefined}
                  className="flex h-[4.5rem] flex-col items-center justify-center gap-1 rounded-[24px] text-xs font-semibold text-on-panel-variant focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-accent"
                >
                  <span className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${active ? 'bg-accent text-on-accent' : ''}`}>
                    <Icon name={d.icon} className="h-5 w-5" />
                  </span>
                  <span className={`max-w-full truncate px-1 ${active ? 'text-on-panel' : ''}`}>{d.short ?? d.label}</span>
                </a>
              </li>
            )
          })}
          {/* "Más" siempre está en el celular: guarda el resto de las pantallas y "Cerrar sesión". */}
          <li className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => setMore(true)}
                aria-haspopup="dialog"
                aria-expanded={more}
                className="flex h-[4.5rem] w-full flex-col items-center justify-center gap-1 rounded-[24px] text-xs font-semibold text-on-panel-variant focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-accent"
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full">
                  <Icon name="menu" className="h-5 w-5" />
                </span>
                <span>{t.nav.more}</span>
              </button>
            </li>
        </ul>
      </nav>

      {more && (
        <MoreSheet
          dests={dests}
          path={path}
          onClose={() => setMore(false)}
          footer={
            <div className="flex items-center justify-between gap-3">
              <p className="min-w-0 truncate text-sm text-on-surface-variant">{user?.full_name}</p>
              {logoutButton()}
            </div>
          }
        />
      )}
      {finding && <QuickFind role={role} onClose={() => setFinding(false)} />}
      {help && <ShortcutsHelp customer={customer} onClose={() => setHelp(false)} />}
    </div>
  )
}
