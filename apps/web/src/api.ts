/** Cliente de la API: token de acceso solo en memoria, refresh por cookie HttpOnly, errores RFC 9457. */
import { t } from './i18n'

export const API = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  title: string
  detail?: string
  errors?: { field: string; message: string }[]

  constructor(status: number, code: string, title: string, detail?: string, errors?: ApiError['errors']) {
    super(detail ? `${title}. ${detail}` : title)
    this.status = status
    this.code = code
    this.title = title
    this.detail = detail
    this.errors = errors
  }

  /** Mensaje para mostrar a la usuaria. */
  get userMessage(): string {
    if (this.errors && this.errors.length > 0) {
      return `${this.title}: ${this.errors.map((e) => e.message).join(', ')}`
    }
    return this.detail ? `${this.title}. ${this.detail}` : this.title
  }
}

let accessToken: string | null = null
let onSessionLost: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler
}

async function toError(resp: Response): Promise<ApiError> {
  try {
    const body = await resp.json()
    return new ApiError(
      resp.status,
      body.code ?? 'error',
      body.title ?? t.genericError,
      body.detail ?? undefined,
      body.errors ?? undefined,
    )
  } catch {
    return new ApiError(resp.status, 'error', t.genericError)
  }
}

export interface TokenResponse {
  access_token: string
  expires_in: number
  user: User
  pyme: Pyme
}

export interface User {
  id: string
  email: string
  full_name: string
  role: 'owner' | 'collaborator'
  is_active: boolean
}

export interface Pyme {
  id: string
  name: string
  default_margin_pct: string | null
  vat_pct: string
  is_demo: boolean
}

let refreshing: Promise<TokenResponse | null> | null = null

/** Pide un token nuevo con la cookie de refresh. Devuelve null si la sesión ya no es válida. */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = fetch(`${API}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (resp) => {
        if (!resp.ok) return null
        const body = (await resp.json()) as TokenResponse
        setAccessToken(body.access_token)
        return body
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let resp: Response
  try {
    resp = await fetch(`${API}${path}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'network_error', t.networkError)
  }
  if (resp.status === 401 && retry && !path.startsWith('/auth/')) {
    const refreshed = await refreshSession()
    if (refreshed) return raw(path, init, false)
    setAccessToken(null)
    onSessionLost?.()
  }
  if (!resp.ok) throw await toError(resp)
  return resp
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await raw(path, init)
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export async function apiBlob(path: string): Promise<Blob> {
  const resp = await raw(path)
  return resp.blob()
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = await post<TokenResponse>('/auth/login', { email, password })
  setAccessToken(body.access_token)
  return body
}

export async function logout(): Promise<void> {
  try {
    await api<void>('/auth/logout', { method: 'POST' })
  } finally {
    setAccessToken(null)
  }
}

// --------------------------------------------------------------------------- tipos de F3

export type OrderUnit = 'unit' | 'dozen' | 'g' | 'kg' | 'ml' | 'l' | 'portion'

export interface RecipeSummary {
  id: string
  name: string
  yield_unit: 'g' | 'ml' | 'unit'
  is_active: boolean
}

export interface Suggestion {
  recipe_id: string
  recipe_name: string
  score: number
}

export interface ExtractedLine {
  requested_name: string
  qty: string
  unit: OrderUnit
  recipe_id: string | null
  recipe_name: string | null
  suggestions: Suggestion[]
  warning: string | null
}

export interface Extraction {
  guests: number | null
  event_date: string | null
  event_date_text: string | null
  lines: ExtractedLine[]
  needs_review: boolean
  extraction: Record<string, unknown>
}

export interface OrderOut {
  id: string
  customer_name: string
  event_date: string | null
  guests: number | null
  status: 'draft' | 'confirmed' | 'delivered' | 'cancelled'
  lines: { id: string; recipe_name: string | null; requested_name: string; qty: string; unit: OrderUnit }[]
  last_quote_id: string | null
}

export interface QuoteProduct {
  recipe_name: string
  qty: string
  unit_label: string
  unit_price_clp: number | null
  subtotal_clp: number | null
}

export interface QuoteOut {
  id: string
  order_id: string
  version: number
  status: 'draft' | 'sent' | 'accepted' | 'rejected'
  valid_until: string | null
  vat_pct: string
  is_complete: boolean
  missing_prices: string[]
  ingredients_cost_clp: number
  net_clp: number
  vat_clp: number
  total_clp: number
  shopping_total_clp: number
  products: QuoteProduct[]
}

export interface ShoppingList {
  groups: {
    supplier_id: string
    supplier_name: string
    delivery_days: number[] | null
    phone: string | null
    total_clp: number
    items: { ingredient_name: string; package_label: string; packages: number; total_clp: number }[]
  }[]
  without_price: string[]
  covered_by_stock: string[]
  total_clp: number
}
