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
      // "customer_name" -> "Nombre del cliente: El texto es demasiado largo (máximo 120 caracteres)"
      const label = (field: string) => t.fields[field.split('.').find((p) => t.fields[p]) ?? ''] ?? null
      const parts = this.errors.map((e) => (label(e.field) ? `${label(e.field)}: ${e.message}` : e.message))
      return `${this.title}. ${parts.join('; ')}`
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
  role: 'owner' | 'collaborator' | 'customer'
  is_active: boolean
}

export interface Pyme {
  id: string
  name: string
  /** No viene en la sesión de un cliente del portal (ADR-007). */
  default_margin_pct?: string | null
  vat_pct: string
  is_demo: boolean
}

let refreshing: Promise<TokenResponse | null> | null = null
let refreshFailedByNetwork = false

/** true si el último refresh falló por falta de red (no por sesión vencida). */
export function lastRefreshFailedByNetwork(): boolean {
  return refreshFailedByNetwork
}

/** Pide un token nuevo con la cookie de refresh. Devuelve null si la sesión ya no es válida. */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = fetch(`${API}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (resp) => {
        refreshFailedByNetwork = false
        if (!resp.ok) return null
        const body = (await resp.json()) as TokenResponse
        setAccessToken(body.access_token)
        return body
      })
      .catch(() => {
        refreshFailedByNetwork = true
        return null
      })
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

export async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
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
  yield_qty?: string
  yield_unit: 'g' | 'ml' | 'unit'
  is_final_product?: boolean
  vision_class?: string | null
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
  status: OrderStatus
  notes?: string | null
  lines: { id: string; recipe_name: string | null; requested_name: string; qty: string; unit: OrderUnit }[]
  last_quote_id: string | null
  last_quote_total_clp?: number | null
  customer_contact?: string | null
  from_customer?: boolean
  submitted_at?: string | null
  owner_message?: string | null
}

export type OrderStatus = 'draft' | 'confirmed' | 'delivered' | 'cancelled' | 'customer_draft' | 'requested'

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

// --------------------------------------------------------------------------- métricas (T09)

export interface MetricStat {
  n: number
  value: number | null
  unit: string
  low_n: boolean
}

export interface BaselineRange {
  first_measured_on: string | null
  last_measured_on: string | null
}

export interface MetricsSummary {
  period: { date_from: string | null; date_to: string; timezone: string }
  low_n_threshold: number
  satisfaction: { n: number; mean_stars: number | null; distribution: Record<string, number>; low_n: boolean }
  quote_time: { caterin_median: MetricStat; manual_median: MetricStat; manual_range: BaselineRange }
  data_lookup: { assistant_median: MetricStat; manual_median: MetricStat; manual_range: BaselineRange }
  assistant: {
    total: number
    levels: { level: number; n: number; p50_ms: number | null; p95_ms: number | null; low_n: boolean }[]
    without_llm: { n: number; total: number; pct: number | null; low_n: boolean }
    degraded: { n: number; total: number; pct: number | null; low_n: boolean }
  }
  warnings: string[]
}

/** Envía el tiempo de una cotización sin bloquear a la usuaria: si falla, se pierde solo la métrica. */
export function sendQuoteTiming(body: {
  started_at: string
  ended_at: string
  quote_id: string
  source: 'text' | 'form'
}): void {
  post('/metrics/quote-timing', body).catch(() => undefined)
}

// --------------------------------------------------------------------------- asistente (T07)

export interface AskSource {
  kind: string
  label: string
}

export interface AskOption {
  label: string
  question: string
}

export interface AskOut {
  interaction_id: string | null
  answer: string
  level: number
  intent: string | null
  status: 'ok' | 'no_data' | 'ambiguous' | 'missing_entity' | 'unrecognized'
  sources: AskSource[]
  options: AskOption[]
  fallback_reason: string | null
  cache_hit: boolean
  latency_ms: number
}

export interface QuickAction {
  id: string
  label: string
  question: string
}

export type AskEvent =
  | { event: 'meta'; data: { sources: AskSource[]; options: AskOption[]; drafting: boolean } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'replace'; data: { text: string; fallback_reason: string } }
  | { event: 'done'; data: AskOut }

function parseSseBlock(block: string): AskEvent | null {
  let event = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!event || !data) return null
  return { event, data: JSON.parse(data) } as AskEvent
}

/** Pregunta al asistente con *streaming* (SSE). Si el servidor responde JSON, entrega un solo `done`. */
export async function askAssistant(
  body: { question: string; quick_action?: string },
  onEvent: (e: AskEvent) => void,
): Promise<AskOut> {
  const resp = await raw('/assistant/ask', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { Accept: 'text/event-stream' },
  })
  if (!(resp.headers.get('Content-Type') ?? '').startsWith('text/event-stream') || !resp.body) {
    const out = (await resp.json()) as AskOut
    onEvent({ event: 'done', data: out })
    return out
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let done: AskOut | null = null
  for (;;) {
    const { value, done: finished } = await reader.read()
    buffer += decoder.decode(value, { stream: !finished })
    let cut = buffer.indexOf('\n\n')
    while (cut >= 0) {
      const ev = parseSseBlock(buffer.slice(0, cut))
      buffer = buffer.slice(cut + 2)
      if (ev) {
        if (ev.event === 'done') done = ev.data
        onEvent(ev)
      }
      cut = buffer.indexOf('\n\n')
    }
    if (finished) break
  }
  if (!done) throw new ApiError(0, 'stream_incomplete', t.assistant.cutOff)
  return done
}

// --------------------------------------------------------------------------- inventario, recetas, ajustes (T08)

export type BaseUnitCode = 'g' | 'ml' | 'unit'

export interface Ingredient {
  id: string
  name: string
  base_unit: BaseUnitCode
  stock_qty: string
  min_stock_qty: string | null
  waste_pct: string | null
  category: string | null
  is_active: boolean
  is_low: boolean
  updated_at: string
}

export interface Movement {
  id: string
  ingredient_id: string
  delta_qty: string
  reason: string
  note: string | null
  occurred_at: string
}

interface Page<T> {
  items: T[]
  next_cursor: string | null
}

/** Todos los insumos activos (la API pagina de a 100 como máximo). */
export async function loadAllIngredients(): Promise<Ingredient[]> {
  const out: Ingredient[] = []
  let cursor: string | null = null
  do {
    const qs: string = cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''
    const page: Page<Ingredient> = await api<Page<Ingredient>>(`/ingredients?limit=100${qs}`)
    out.push(...page.items)
    cursor = page.next_cursor
  } while (cursor)
  return out
}

export async function loadMovements(ingredientId: string): Promise<Movement[]> {
  return (await api<Page<Movement>>(`/ingredients/${ingredientId}/movements?limit=20`)).items
}

export interface RecipeLine {
  id: string
  ingredient_id: string
  ingredient_name: string
  base_unit: BaseUnitCode | null
  qty: string
  waste_pct: string | null
}

export interface RecipeDetail {
  id: string
  name: string
  yield_qty: string
  yield_unit: BaseUnitCode
  is_final_product: boolean
  vision_class: string | null
  notes: string | null
  version: number
  is_active: boolean
  lines: RecipeLine[]
}

export interface RecipeCost {
  recipe_name: string
  units: string
  yield_unit: BaseUnitCode
  total_clp: number
  per_unit_clp: number | null
  is_complete: boolean
  missing_prices: string[]
  lines: {
    ingredient_name: string
    base_unit: BaseUnitCode
    required_qty: string
    supplier_name: string | null
    package_label: string | null
    price_date: string | null
    cost_clp: number | null
  }[]
}

export interface PymeSettings {
  id: string
  name: string
  rut: string | null
  commune: string | null
  default_waste_pct: string
  default_margin_pct: string | null
  vat_pct: string
  prices_include_vat: boolean
  quote_validity_days: number | null
  is_demo: boolean
  customer_code?: string | null
}

export interface CountLine {
  vision_class: string
  count: number
  recipe_id: string | null
  recipe_name: string | null
}

export interface CountOut {
  model_version: string
  counts: CountLine[]
  detections: { vision_class: string; score: number; box: [number, number, number, number] }[]
  elapsed_ms: number
}

export async function countPhoto(image: Blob): Promise<CountOut> {
  const form = new FormData()
  form.append('image', image, 'bandeja.jpg')
  return api<CountOut>('/vision/count', { method: 'POST', body: form })
}

export interface RowIssue {
  row: number
  field: string
  message: string
}

export interface ImportPreview<Row> {
  total_rows: number
  valid: Row[]
  errors: RowIssue[]
  source?: string
}

export interface ImportResult {
  import_batch_id: string
  created: number
  suppliers_created: number
}

export async function registerAccount(body: {
  pyme_name: string
  full_name: string
  email: string
  password: string
}): Promise<TokenResponse> {
  const out = await post<TokenResponse>('/auth/register', body)
  setAccessToken(out.access_token)
  return out
}

// --------------------------------------------------------------------------- portal de clientes (ADR-007)

export interface PortalPyme {
  id: string
  name: string
  commune: string | null
  joined: boolean
}

export interface PortalProduct {
  id: string
  name: string
  yield_unit: 'g' | 'ml' | 'unit'
}

export interface CustomerQuote {
  version: number
  is_complete: boolean
  products: { name: string; qty: string; unit_label: string; unit_price_clp: number | null; subtotal_clp: number | null }[]
  net_clp: number | null
  vat_pct: string
  vat_clp: number | null
  total_clp: number | null
  valid_until: string | null
}

export interface PortalRequest {
  id: string
  pyme_id: string
  pyme_name: string
  status: OrderStatus
  created_at: string
  submitted_at: string | null
  decided_at: string | null
  event_date: string | null
  guests: number | null
  notes: string | null
  owner_message: string | null
  lines: { name: string; qty: string; unit: OrderUnit; unit_label: string }[]
  quote: CustomerQuote | null
  price_pending: 'margin_required' | 'missing_prices' | 'cannot_calculate' | null
  can_send: boolean
  can_cancel: boolean
}

export interface PortalRequestSummary {
  id: string
  pyme_id: string
  pyme_name: string
  status: OrderStatus
  created_at: string
  submitted_at: string | null
  event_date: string | null
  products: string
  total_clp: number | null
}

export async function registerCustomer(body: {
  code?: string
  pyme_id?: string
  full_name: string
  email: string
  password: string
}): Promise<TokenResponse> {
  const out = await post<TokenResponse>('/portal/register', body)
  setAccessToken(out.access_token)
  return out
}

/** Enlace que la dueña comparte con sus clientes para que se registren en el portal. */
export function customerLink(code: string): string {
  return `${window.location.origin}${window.location.pathname}#/cliente/${encodeURIComponent(code)}`
}
