import { useMemo, useState } from 'react'
import type { PortalPyme } from '../../api'
import { Alert, Page, Spinner, inputClass } from '../../components/ui'
import { Icon } from '../../components/Icon'
import { t } from '../../i18n'
import { useCached } from '../../offline/cache'
import { navigate } from '../../router'
import { plain, savedAtLabel } from '../Inventory'

/** Logo de la pyme o, si no tiene, un círculo con su inicial. Decorativo: el nombre va al lado. */
export function PymeAvatar({ pyme, size = 'md' }: { pyme: Pick<PortalPyme, 'name' | 'logo_url'>; size?: 'md' | 'lg' }) {
  const box = size === 'lg' ? 'h-20 w-20 text-3xl' : 'h-14 w-14 text-2xl'
  if (pyme.logo_url) {
    return <img src={pyme.logo_url} alt="" className={`${box} shrink-0 rounded-xl object-cover`} />
  }
  return (
    <span
      aria-hidden="true"
      className={`${box} inline-flex shrink-0 items-center justify-center rounded-xl bg-primary-container font-display font-semibold text-on-primary-container`}
    >
      {pyme.name.trim().charAt(0).toUpperCase()}
    </span>
  )
}

/** Catálogo del portal (T15, ADR-009): las pymes a las que el cliente puede cotizar. */
export default function PortalPymes() {
  const { value, error, loading } = useCached<PortalPyme[]>('portal:pymes', '/portal/pymes')
  const [query, setQuery] = useState('')
  const all = value?.data
  const items = useMemo(() => {
    const q = plain(query)
    return (all ?? []).filter((p) => !q || plain(p.name).includes(q) || plain(p.commune ?? '').includes(q))
  }, [all, query])

  return (
    <Page title={t.catalog.title} onBack={() => navigate('/')}>
      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      <p className="mb-4 max-w-prose text-on-surface-variant">{t.catalog.intro}</p>
      {all && all.length > 3 && (
        <div className="mb-4 max-w-md">
          <label htmlFor="pymes-search" className="mb-1 block font-medium text-on-surface">
            {t.catalog.search}
          </label>
          <input
            id="pymes-search"
            type="search"
            className={inputClass}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      )}
      {error && !value && <Alert>{error.userMessage}</Alert>}
      {loading && !value ? (
        <Spinner label={t.loading} />
      ) : all && all.length === 0 ? (
        <Alert kind="info">{t.portal.noPymes}</Alert>
      ) : items.length === 0 && query ? (
        <p className="text-on-surface-variant">{t.catalog.noResults(query)}</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((p) => (
            <li key={p.id}>
              <a
                href={`#/pymes/${p.id}`}
                className="flex h-full gap-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-4 transition hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30"
              >
                <PymeAvatar pyme={p} />
                <span className="min-w-0 flex-1">
                  <span className="block text-lg font-medium text-on-surface">{p.name}</span>
                  {p.commune && <span className="block text-on-surface-variant">{p.commune}</span>}
                  {p.description && (
                    <span className="mt-1 line-clamp-2 block text-sm text-on-surface-variant">{p.description}</span>
                  )}
                  {p.joined && (
                    <span className="mt-2 inline-flex h-7 items-center rounded-lg bg-secondary-container px-2 text-sm font-medium text-on-secondary-container">
                      {t.portal.joined}
                    </span>
                  )}
                </span>
                <Icon name="store" className="mt-1 h-6 w-6 shrink-0 text-on-surface-variant" />
              </a>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
