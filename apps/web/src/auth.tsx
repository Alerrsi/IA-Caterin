import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as client from './api'

interface AuthState {
  status: 'loading' | 'anonymous' | 'authenticated'
  user: client.User | null
  pyme: client.Pyme | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading')
  const [user, setUser] = useState<client.User | null>(null)
  const [pyme, setPyme] = useState<client.Pyme | null>(null)

  const apply = useCallback((session: client.TokenResponse | null) => {
    setUser(session?.user ?? null)
    setPyme(session?.pyme ?? null)
    setStatus(session ? 'authenticated' : 'anonymous')
  }, [])

  useEffect(() => {
    client.setSessionLostHandler(() => apply(null))
    client.refreshSession().then(apply)
    return () => client.setSessionLostHandler(null)
  }, [apply])

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      pyme,
      login: async (email, password) => apply(await client.login(email, password)),
      logout: async () => {
        await client.logout().catch(() => undefined)
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
