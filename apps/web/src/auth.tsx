import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as client from './api'
import { setScope } from './offline/db'
import { startSync } from './offline/queue'

interface AuthState {
  status: 'loading' | 'anonymous' | 'authenticated'
  user: client.User | null
  pyme: client.Pyme | null
  login: (email: string, password: string) => Promise<void>
  register: (data: Parameters<typeof client.registerAccount>[0]) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)
const LAST_SESSION = 'caterin:last-session' // usuaria y pyme, SIN tokens: para abrir la app sin señal

function remember(session: client.TokenResponse | null): void {
  try {
    if (session) localStorage.setItem(LAST_SESSION, JSON.stringify({ user: session.user, pyme: session.pyme }))
    else localStorage.removeItem(LAST_SESSION)
  } catch {
    /* almacenamiento bloqueado: sin modo offline */
  }
}

function lastSession(): client.TokenResponse | null {
  try {
    const raw = localStorage.getItem(LAST_SESSION)
    return raw ? { access_token: '', expires_in: 0, ...JSON.parse(raw) } : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading')
  const [user, setUser] = useState<client.User | null>(null)
  const [pyme, setPyme] = useState<client.Pyme | null>(null)

  const apply = useCallback((session: client.TokenResponse | null) => {
    setScope(session?.pyme.id ?? null) // los datos guardados en el teléfono son por pyme
    if (session?.access_token) remember(session)
    setUser(session?.user ?? null)
    setPyme(session?.pyme ?? null)
    setStatus(session ? 'authenticated' : 'anonymous')
  }, [])

  useEffect(() => {
    client.setSessionLostHandler(() => apply(null))
    client.refreshSession().then((session) => {
      // Sin señal no se puede renovar la sesión: se abre con la última conocida y se renueva al volver la red.
      if (!session && client.lastRefreshFailedByNetwork()) apply(lastSession())
      else apply(session)
    })
    return () => client.setSessionLostHandler(null)
  }, [apply])

  useEffect(() => {
    if (status !== 'authenticated') return
    return startSync() // envía la cola de cambios hechos sin señal (ADR-004)
  }, [status, pyme?.id])

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      pyme,
      login: async (email, password) => apply(await client.login(email, password)),
      register: async (data) => apply(await client.registerAccount(data)),
      logout: async () => {
        await client.logout().catch(() => undefined)
        remember(null)
        apply(null)
      },
    }),
    [status, user, pyme, apply],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth fuera de AuthProvider')
  return ctx
}
