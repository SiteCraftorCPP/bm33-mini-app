import { mockCatalog } from './mockData'
import type { Catalog, CheckoutData, OrderDetail, OrderSummary, PromoCode, UserProfile } from './types'

const headers = (): HeadersInit => ({
  'Content-Type': 'application/json',
  'X-Telegram-Init-Data': window.Telegram?.WebApp.initData ?? '',
  'X-Demo-User-Id': '100001',
})

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...options?.headers } })
  if (response.status === 204) {
    return undefined as T
  }
  if (!response.ok) {
    let message = 'Что-то пошло не так'
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      const detail = payload.detail
      if (typeof detail === 'string') message = detail
      else if (Array.isArray(detail) && detail[0]?.msg) message = detail[0].msg
    } catch {
      // Keep the friendly default.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function loadPublicConfig(): Promise<{ managerTelegramUrl: string }> {
  try {
    return await request<{ managerTelegramUrl: string }>('/api/config')
  } catch {
    const username = (import.meta.env.VITE_MANAGER_USERNAME as string | undefined)?.replace(/^@/, '')
    return { managerTelegramUrl: username ? `https://t.me/${username}` : '' }
  }
}

export async function loadCatalog(): Promise<{ catalog: Catalog; offline: boolean }> {
  try {
    const catalog = await request<Catalog>('/api/catalog')
    if (!catalog.products.length) throw new Error('Пустой каталог')
    return { catalog, offline: false }
  } catch {
    return { catalog: mockCatalog, offline: true }
  }
}

export async function loadProfile(): Promise<UserProfile | null> {
  try {
    return await request<UserProfile>('/api/me')
  } catch {
    return null
  }
}

export async function createOrder(
  data: CheckoutData,
  items: Array<{ variantId: string; quantity: number }>,
): Promise<{ id: number; status: string; total: number }> {
  return request('/api/orders', {
    method: 'POST',
    body: JSON.stringify({ ...data, items }),
  })
}

export async function subscribeToRestock(variantId: string): Promise<void> {
  await request('/api/subscriptions', {
    method: 'POST',
    body: JSON.stringify({ variantId }),
  })
}

export async function loadOrders(): Promise<OrderSummary[]> {
  const payload = await request<{ orders: OrderSummary[] }>('/api/orders')
  return payload.orders
}

export async function loadOrder(orderId: number): Promise<OrderDetail> {
  return request<OrderDetail>(`/api/orders/${orderId}`)
}

export async function cancelOrder(orderId: number): Promise<{ id: number; status: string; statusLabel: string }> {
  return request(`/api/orders/${orderId}/cancel`, { method: 'POST' })
}

export async function adminSyncCatalog(): Promise<{
  products: number
  restocked: number
  stickWarnings: string[]
  imageCachePending?: boolean
}> {
  const payload = await request<{
    ok: boolean
    products: number
    restocked: number
    stickWarnings?: string[]
    imageCachePending?: boolean
  }>('/api/admin/catalog/sync', { method: 'POST' })
  return {
    products: payload.products,
    restocked: payload.restocked,
    stickWarnings: payload.stickWarnings ?? [],
    imageCachePending: payload.imageCachePending ?? false,
  }
}

export async function adminLoadOrders(): Promise<OrderSummary[]> {
  const payload = await request<{ orders: OrderSummary[] }>('/api/admin/orders')
  return payload.orders
}

export async function validatePromo(
  code: string,
  subtotal: number,
): Promise<{ code: string; discount: number; total: number }> {
  return request('/api/promos/validate', {
    method: 'POST',
    body: JSON.stringify({ code, subtotal }),
  })
}

export async function adminLoadPromos(): Promise<PromoCode[]> {
  const payload = await request<{ promos: PromoCode[] }>('/api/admin/promos')
  return payload.promos
}

export async function adminCreatePromo(data: {
  code: string
  kind: 'percent' | 'fixed'
  value: number
  maxUses?: number | null
  note?: string
}): Promise<PromoCode> {
  return request('/api/admin/promos', {
    method: 'POST',
    body: JSON.stringify({
      code: data.code,
      kind: data.kind,
      value: data.value,
      maxUses: data.maxUses ?? null,
      note: data.note ?? '',
    }),
  })
}

export async function adminPatchPromo(
  code: string,
  patch: { active?: boolean; maxUses?: number | null; note?: string },
): Promise<PromoCode> {
  return request(`/api/admin/promos/${encodeURIComponent(code)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function adminDeletePromo(code: string): Promise<void> {
  await request<void>(`/api/admin/promos/${encodeURIComponent(code)}`, { method: 'DELETE' })
}

