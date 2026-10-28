export type Category = {
  id: string
  name: string
  count: number
}

export type Variant = {
  id: string
  option1Name: string
  option1Value: string
  option2Name: string
  option2Value: string
  side: string
  label: string
  stock: number
  price: number
}

export type Product = {
  id: string
  name: string
  category: string
  description: string
  imageUrl: string
  stock: number
  minPrice: number
  variants: Variant[]
}

export type Catalog = {
  categories: Category[]
  products: Product[]
}

export type CartLine = {
  product: Product
  variant: Variant
  quantity: number
}

export type View = 'home' | 'catalog' | 'cart' | 'checkout' | 'success' | 'orders' | 'admin'

export type CheckoutData = {
  customerName: string
  phone: string
  city: string
  delivery: string
  comment: string
  promoCode: string
}

export type PromoCode = {
  code: string
  kind: 'percent' | 'fixed'
  value: number
  maxUses: number | null
  usedCount: number
  active: boolean
  note: string
  createdAt: string
}

export type UserProfile = {
  id: number
  username: string
  firstName: string
  isDemo: boolean
  isAdmin: boolean
}

export type OrderSummary = {
  id: number
  status: string
  statusLabel: string
  total: number
  createdAt: string
  itemCount: number
  customerName?: string
  phone?: string
  telegramUserId?: number
}

export type OrderDetail = OrderSummary & {
  customerName: string
  phone: string
  city: string
  comment: string
  items: Array<{
    name: string
    variant: string
    quantity: number
    price: number
  }>
}

export type CatalogFilterGroup = {
  key: string
  label: string
  values: string[]
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        initDataUnsafe?: { start_param?: string }
        colorScheme: 'light' | 'dark'
        ready: () => void
        expand: () => void
        close: () => void
        openTelegramLink: (url: string) => void
        addToHomeScreen?: () => void
        checkHomeScreenStatus?: () => void
        onEvent?: (event: string, handler: (payload: { status?: string }) => void) => void
        HapticFeedback?: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy') => void
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void
        }
      }
    }
  }
}

