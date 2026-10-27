import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Home,
  LayoutGrid,
  MapPin,
  Menu,
  MessageCircle,
  Minus,
  Phone,
  Plus,
  Search,
  RefreshCw,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  SlidersHorizontal,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react'
import {
  adminLoadOrders,
  adminSyncCatalog,
  createOrder,
  loadCatalog,
  loadOrder,
  loadOrders,
  loadProfile,
  loadPublicConfig,
} from './api'
import { filterGroupsForCategory, productMatchesFilters } from './catalogFilters'
import { formatModelCount } from './pluralRu'
import { CategoryIcon } from './components/CategoryIcon'
import { ProductCard } from './components/ProductCard'
import { ProductSheet } from './components/ProductSheet'
import { ProductVisual } from './components/ProductVisual'
import { checkHomeScreenStatus, homeScreenSupported, requestAddToHomeScreen } from './homeScreen'
import type { CartLine, Catalog, CheckoutData, OrderDetail, OrderSummary, Product, UserProfile, Variant, View } from './types'

const money = new Intl.NumberFormat('ru-RU')

const emptyCheckout: CheckoutData = {
  customerName: '',
  phone: '',
  city: '',
  delivery: '',
  comment: '',
}

function App() {
  const [catalog, setCatalog] = useState<Catalog>({ categories: [], products: [] })
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  const [view, setView] = useState<View>('home')
  const [activeCategory, setActiveCategory] = useState('Все')
  const [query, setQuery] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [categoryFilters, setCategoryFilters] = useState<Record<string, string>>({})
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [focusOrderId, setFocusOrderId] = useState<number | null>(null)
  const [cart, setCart] = useState<CartLine[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('ches-cart') || '[]') as CartLine[]
    } catch {
      return []
    }
  })
  const [checkout, setCheckout] = useState<CheckoutData>(emptyCheckout)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [orderId, setOrderId] = useState<number | null>(null)
  const [managerTelegramUrl, setManagerTelegramUrl] = useState('')

  useEffect(() => {
    Promise.all([loadCatalog(), loadProfile(), loadPublicConfig()]).then(
      ([{ catalog: next, offline: isOffline }, me, config]) => {
        setCatalog(next)
        setOffline(isOffline)
        setProfile(me)
        setManagerTelegramUrl(config.managerTelegramUrl)
        setLoading(false)
      },
    )
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const fromQuery = params.get('order')
    const startParam = window.Telegram?.WebApp.initDataUnsafe?.start_param
    const fromStart =
      startParam?.startsWith('order_') ? startParam.slice('order_'.length) : startParam
    const raw = fromQuery || fromStart
    if (raw && /^\d+$/.test(raw)) {
      setFocusOrderId(Number(raw))
      setView('orders')
    }
  }, [])

  useEffect(() => {
    setCategoryFilters({})
    setFiltersOpen(false)
  }, [activeCategory])

  useEffect(() => {
    localStorage.setItem('ches-cart', JSON.stringify(cart))
  }, [cart])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [view, activeCategory])

  const cartCount = cart.reduce((sum, line) => sum + line.quantity, 0)
  const cartTotal = cart.reduce((sum, line) => sum + line.variant.price * line.quantity, 0)

  const filterGroups = useMemo(
    () => filterGroupsForCategory(activeCategory, catalog.products),
    [activeCategory, catalog.products],
  )

  const visibleProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('ru')
    return catalog.products.filter((product) => {
      if (activeCategory !== 'Все' && product.category !== activeCategory) return false
      if (normalizedQuery && !product.name.toLocaleLowerCase('ru').includes(normalizedQuery)) return false
      return productMatchesFilters(product, categoryFilters)
    })
  }, [activeCategory, catalog, query, categoryFilters])

  const goCatalog = (category = 'Все') => {
    setActiveCategory(category)
    setView('catalog')
  }

  const addToCart = (product: Product, variant: Variant, quantity: number) => {
    setCart((current) => {
      const existing = current.find((line) => line.variant.id === variant.id)
      if (existing) {
        return current.map((line) =>
          line.variant.id === variant.id
            ? { ...line, quantity: Math.min(variant.stock, line.quantity + quantity) }
            : line,
        )
      }
      return [...current, { product, variant, quantity: Math.min(variant.stock, quantity) }]
    })
    window.Telegram?.WebApp.HapticFeedback?.impactOccurred('medium')
  }

  const setLineQuantity = (variantId: string, quantity: number) => {
    setCart((current) =>
      current
        .map((line) =>
          line.variant.id === variantId
            ? { ...line, quantity: Math.min(line.variant.stock, Math.max(0, quantity)) }
            : line,
        )
        .filter((line) => line.quantity > 0),
    )
  }

  const submitOrder = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const result = offline
        ? { id: Math.floor(1000 + Math.random() * 9000), status: 'new', total: cartTotal }
        : await createOrder(
            checkout,
            cart.map((line) => ({ variantId: line.variant.id, quantity: line.quantity })),
          )
      setOrderId(result.id)
      setCart([])
      setView('success')
      window.Telegram?.WebApp.HapticFeedback?.notificationOccurred('success')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось оформить заказ')
      window.Telegram?.WebApp.HapticFeedback?.notificationOccurred('error')
    } finally {
      setSubmitting(false)
    }
  }

  const openSupport = () => {
    const fallback = (import.meta.env.VITE_MANAGER_USERNAME as string | undefined)?.replace(/^@/, '')
    const url =
      managerTelegramUrl || (fallback ? `https://t.me/${fallback}` : '')
    if (!url) {
      setError('Контакт менеджера не настроен')
      return
    }
    if (window.Telegram?.WebApp) window.Telegram.WebApp.openTelegramLink(url)
    else window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="app-shell">
      {offline && (
        <div className="demo-banner">
          <WifiOff size={14} /> Демо-каталог · подключите backend для актуальных остатков
        </div>
      )}

      <header className="topbar">
        <button className="brand" onClick={() => setView('home')}>
          <span className="brand-mark">CH</span>
          <span><strong>CHES</strong><small>HOCKEY STORE</small></span>
        </button>
        <button className="icon-button" onClick={() => goCatalog()} aria-label="Каталог">
          <Menu size={21} />
        </button>
      </header>

      <main>
        {loading ? (
          <LoadingScreen />
        ) : view === 'home' ? (
          <HomeView
            catalog={catalog}
            onCategory={goCatalog}
            onProduct={setSelectedProduct}
            onCatalog={() => goCatalog()}
          />
        ) : view === 'catalog' ? (
          <CatalogView
            catalog={catalog}
            activeCategory={activeCategory}
            setActiveCategory={setActiveCategory}
            query={query}
            setQuery={setQuery}
            products={visibleProducts}
            onProduct={setSelectedProduct}
            filtersOpen={filtersOpen}
            setFiltersOpen={setFiltersOpen}
            filterGroups={filterGroups}
            categoryFilters={categoryFilters}
            setCategoryFilters={setCategoryFilters}
          />
        ) : view === 'orders' ? (
          <OrdersView
            offline={offline}
            focusOrderId={focusOrderId}
            onBack={() => {
              setFocusOrderId(null)
              setView('home')
            }}
          />
        ) : view === 'admin' ? (
          profile?.isAdmin ? (
            <AdminView
              offline={offline}
              onCatalogRefresh={async () => {
                const { catalog: next } = await loadCatalog()
                setCatalog(next)
              }}
            />
          ) : (
            <div className="empty-state page">
              <strong>Нет доступа</strong>
              <p>Раздел только для администраторов магазина.</p>
            </div>
          )
        ) : view === 'cart' ? (
          <CartView
            cart={cart}
            total={cartTotal}
            onQuantity={setLineQuantity}
            onCatalog={() => goCatalog()}
            onCheckout={() => setView('checkout')}
          />
        ) : view === 'checkout' ? (
          <CheckoutView
            data={checkout}
            setData={setCheckout}
            cart={cart}
            total={cartTotal}
            submitting={submitting}
            error={error}
            onBack={() => setView('cart')}
            onSubmit={submitOrder}
          />
        ) : (
          <SuccessView orderId={orderId} offline={offline} onHome={() => setView('home')} onSupport={openSupport} />
        )}
      </main>

      {!['checkout', 'success'].includes(view) && (
        <BottomNav
          view={view}
          cartCount={cartCount}
          isAdmin={Boolean(profile?.isAdmin)}
          onHome={() => setView('home')}
          onCatalog={() => goCatalog(activeCategory)}
          onCart={() => setView('cart')}
          onAdmin={() => setView('admin')}
          onSupport={openSupport}
        />
      )}

      <ProductSheet product={selectedProduct} onClose={() => setSelectedProduct(null)} onAdd={addToCart} />
    </div>
  )
}

function HomeView({
  catalog,
  onCategory,
  onProduct,
  onCatalog,
}: {
  catalog: Catalog
  onCategory: (category: string) => void
  onProduct: (product: Product) => void
  onCatalog: () => void
}) {
  const [showShortcut, setShowShortcut] = useState(homeScreenSupported())

  useEffect(() => {
    if (!homeScreenSupported()) return
    checkHomeScreenStatus().then((status) => {
      if (status === 'added') setShowShortcut(false)
    })
  }, [])

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-kicker"><span /> ЭКИПИРОВКА, КОТОРАЯ РЕШАЕТ</span>
          <h1>Твой лёд.<br /><em>Твои правила.</em></h1>
          <p>Профессиональная хоккейная экипировка в наличии. Подберём вариант под вашу игру.</p>
          <button className="hero-button" onClick={onCatalog}>
            Смотреть каталог <ArrowRight size={18} />
          </button>
        </div>
        <div className="hero-stripe" />
      </section>

      {showShortcut && (
        <section className="home-shortcut">
          <button
            type="button"
            className="home-shortcut__button"
            onClick={() => {
              requestAddToHomeScreen()
              window.Telegram?.WebApp.HapticFeedback?.impactOccurred('light')
            }}
          >
            <Smartphone size={20} />
            <span>
              <strong>Ярлык на главный экран</strong>
              <small>Быстрый вход в магазин, как отдельное приложение</small>
            </span>
          </button>
          <p className="home-shortcut__hint">Или меню ⋮ в Telegram → «Создать ярлык»</p>
        </section>
      )}

      <section className="content-section category-section">
        <div className="section-heading">
          <div><h2>Категории</h2></div>
          <button onClick={onCatalog}>Все <ChevronRight size={16} /></button>
        </div>
        <div className="category-rail">
          {catalog.categories.map((category, index) => {
            return (
              <button className={`category-tile tile-${index}`} key={category.id} onClick={() => onCategory(category.name)}>
                <CategoryIcon category={category.name} />
                <strong>{category.name}</strong>
                <small>{formatModelCount(category.count)}</small>
                <ArrowRight className="tile-arrow" size={16} />
              </button>
            )
          })}
        </div>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <div><h2>В центре игры</h2></div>
          <button onClick={onCatalog}>Каталог <ChevronRight size={16} /></button>
        </div>
        <div className="product-grid">
          {catalog.products.filter((product) => product.stock > 0).slice(0, 6).map((product) => (
            <ProductCard product={product} onOpen={onProduct} key={product.id} />
          ))}
        </div>
      </section>

      <section className="service-card">
        <span className="service-icon"><ShieldCheck size={28} /></span>
        <div><strong>Поможем с выбором</strong><p>Менеджер проверит параметры и свяжется после заказа.</p></div>
        <span className="service-number">24/7</span>
      </section>
    </>
  )
}

function CatalogView({
  catalog,
  activeCategory,
  setActiveCategory,
  query,
  setQuery,
  products,
  onProduct,
  filtersOpen,
  setFiltersOpen,
  filterGroups,
  categoryFilters,
  setCategoryFilters,
}: {
  catalog: Catalog
  activeCategory: string
  setActiveCategory: (value: string) => void
  query: string
  setQuery: (value: string) => void
  products: Product[]
  onProduct: (product: Product) => void
  filtersOpen: boolean
  setFiltersOpen: (value: boolean) => void
  filterGroups: import('./types').CatalogFilterGroup[]
  categoryFilters: Record<string, string>
  setCategoryFilters: (value: Record<string, string>) => void
}) {
  const filterCount = Object.values(categoryFilters).filter(Boolean).length
  const filtersAvailable = activeCategory !== 'Все' && filterGroups.length > 0
  return (
    <section className="catalog-page page">
      <div className="page-title">
        <span className="eyebrow">CHES / STORE</span>
        <h1>Каталог</h1>
        <p>{formatModelCount(products.length)} под вашу игру</p>
      </div>

      <div className="search-row">
        <label className="search-box">
          <Search size={19} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти модель" />
          {query && <button onClick={() => setQuery('')}><X size={16} /></button>}
        </label>
        {filtersAvailable && (
          <button className={`filter-button ${filterCount ? 'is-active' : ''}`} onClick={() => setFiltersOpen(!filtersOpen)}>
            <SlidersHorizontal size={19} />
            {filterCount > 0 && <span>{filterCount}</span>}
          </button>
        )}
      </div>

      <div className="catalog-categories">
        {['Все', ...catalog.categories.map((category) => category.name)].map((category) => (
          <button
            className={activeCategory === category ? 'is-active' : ''}
            key={category}
            onClick={() => setActiveCategory(category)}
          >
            {category}
          </button>
        ))}
      </div>

      {filtersOpen && filtersAvailable && (
        <div className="filters-panel">
          <div className="filters-head">
            <strong>Фильтры · {activeCategory}</strong>
            <button onClick={() => setCategoryFilters({})}>Сбросить</button>
          </div>
          {filterGroups.map((group) => (
            <div className="filter-group" key={group.key}>
              <span>{group.label}</span>
              <div>
                {group.values.map((value) => (
                  <button
                    key={value}
                    className={categoryFilters[group.key] === value ? 'is-selected' : ''}
                    onClick={() =>
                      setCategoryFilters({
                        ...categoryFilters,
                        [group.key]: categoryFilters[group.key] === value ? '' : value,
                      })
                    }
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="catalog-meta">
        <strong>{activeCategory}</strong>
        <span>{products.length} товаров</span>
      </div>

      {products.length ? (
        <div className="product-grid">
          {products.map((product) => <ProductCard product={product} onOpen={onProduct} key={product.id} />)}
        </div>
      ) : (
        <div className="empty-state">
          <Search size={32} />
          <strong>Ничего не нашли</strong>
          <p>Измените запрос или сбросьте фильтры.</p>
          <button onClick={() => { setQuery(''); setCategoryFilters({}) }}>Сбросить</button>
        </div>
      )}
    </section>
  )
}

function CartView({
  cart,
  total,
  onQuantity,
  onCatalog,
  onCheckout,
}: {
  cart: CartLine[]
  total: number
  onQuantity: (variantId: string, quantity: number) => void
  onCatalog: () => void
  onCheckout: () => void
}) {
  return (
    <section className="page cart-page">
      <div className="page-title inline">
        <div><span className="eyebrow">ВАШ ВЫБОР</span><h1>Корзина</h1></div>
        <span className="cart-big-count">{cart.reduce((sum, line) => sum + line.quantity, 0)}</span>
      </div>
      {cart.length === 0 ? (
        <div className="empty-cart">
          <span><ShoppingBag size={42} strokeWidth={1.3} /></span>
          <h2>Пока пусто</h2>
          <p>Добавьте экипировку — всё сохранится здесь.</p>
          <button className="primary-button" onClick={onCatalog}>Перейти в каталог</button>
        </div>
      ) : (
        <>
          <div className="cart-list">
            {cart.map((line) => (
              <article className="cart-line" key={line.variant.id}>
                <ProductVisual category={line.product.category} imageUrl={line.product.imageUrl} compact />
                <div className="cart-line-info">
                  <span className="eyebrow">{line.product.category}</span>
                  <strong>{line.product.name.replace(/\s[LR](?=\s|$)/, '')}</strong>
                  <small>{line.variant.label}</small>
                  <div className="cart-line-bottom">
                    <b>{money.format(line.variant.price * line.quantity)} ₽</b>
                    <div className="mini-stepper">
                      <button onClick={() => onQuantity(line.variant.id, line.quantity - 1)}>
                        {line.quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}
                      </button>
                      <span>{line.quantity}</span>
                      <button
                        disabled={line.quantity >= line.variant.stock}
                        onClick={() => onQuantity(line.variant.id, line.quantity + 1)}
                      ><Plus size={14} /></button>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <div className="cart-summary">
            <div><span>Товары</span><strong>{money.format(total)} ₽</strong></div>
            <div className="summary-total"><span>Итого</span><strong>{money.format(total)} ₽</strong></div>
            <p><ShieldCheck size={16} /> Остатки проверим ещё раз перед оформлением</p>
          </div>
          <div className="cart-checkout-bar">
            <div><span>Итого</span><strong>{money.format(total)} ₽</strong></div>
            <button className="primary-button" onClick={onCheckout}>Оформить <ArrowRight size={18} /></button>
          </div>
        </>
      )}
    </section>
  )
}

function CheckoutView({
  data,
  setData,
  cart,
  total,
  submitting,
  error,
  onBack,
  onSubmit,
}: {
  data: CheckoutData
  setData: (value: CheckoutData) => void
  cart: CartLine[]
  total: number
  submitting: boolean
  error: string
  onBack: () => void
  onSubmit: (event: FormEvent) => void
}) {
  const update = (field: keyof CheckoutData, value: string) => setData({ ...data, [field]: value })
  return (
    <section className="page checkout-page">
      <button className="back-link" onClick={onBack}><ArrowLeft size={18} /> Корзина</button>
      <div className="page-title"><span className="eyebrow">ПОСЛЕДНИЙ ШАГ</span><h1>Оформление</h1><p>Менеджер свяжется с вами в Telegram</p></div>
      <form onSubmit={onSubmit}>
        <div className="form-card">
          <h3><span>01</span> Контакты</h3>
          <label><CircleUserRound size={18} /><span><small>Ваше имя</small><input required minLength={2} value={data.customerName} onChange={(e) => update('customerName', e.target.value)} placeholder="Александр" /></span></label>
          <label><Phone size={18} /><span><small>Телефон</small><input required minLength={5} value={data.phone} onChange={(e) => update('phone', e.target.value)} placeholder="+7 999 000-00-00" inputMode="tel" /></span></label>
          <label><MapPin size={18} /><span><small>Город</small><input value={data.city} onChange={(e) => update('city', e.target.value)} placeholder="Москва" /></span></label>
        </div>
        <div className="form-card">
          <h3><span>02</span> Детали</h3>
          <label className="comment-field"><MessageCircle size={18} /><span><small>Комментарий</small><textarea value={data.comment} onChange={(e) => update('comment', e.target.value)} placeholder="Размер, доставка, пожелания" rows={4} /></span></label>
        </div>
        <div className="order-mini-summary">
          <span>{cart.reduce((sum, line) => sum + line.quantity, 0)} товара</span>
          <strong>{money.format(total)} ₽</strong>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button checkout-submit" disabled={submitting || !cart.length}>
          {submitting ? 'Проверяем остатки…' : 'Подтвердить заказ'} {!submitting && <ArrowRight size={18} />}
        </button>
        <p className="form-note">Нажимая кнопку, вы отправляете заявку менеджеру в группу магазина. Оплата и доставка — только в переписке с менеджером.</p>
      </form>
    </section>
  )
}

function SuccessView({
  orderId,
  offline,
  onHome,
  onSupport,
}: {
  orderId: number | null
  offline: boolean
  onHome: () => void
  onSupport: () => void
}) {
  return (
    <section className="success-page">
      <div className="success-orbit"><span><CheckCircle2 size={46} /></span></div>
      <span className="eyebrow">ЗАЯВКА ПРИНЯТА</span>
      <h1>Заказ №{orderId}<br />уже у менеджера</h1>
      <p>{offline ? 'Это демонстрационный заказ — он не отправлен менеджеру.' : 'Заявка ушла менеджерам. Все вопросы — в личке с менеджером в Telegram.'}</p>
      <div className="success-steps">
        <div className="is-done"><span>1</span><strong>Заказ создан</strong></div>
        <div><span>2</span><strong>Связь с менеджером</strong></div>
        <div><span>3</span><strong>Отправка</strong></div>
      </div>
      <button className="primary-button" onClick={onHome}>Вернуться на главную</button>
      <button className="text-button" onClick={onSupport}><MessageCircle size={17} /> Написать менеджеру</button>
    </section>
  )
}

function OrdersView({
  offline,
  focusOrderId,
  onBack,
}: {
  offline: boolean
  focusOrderId: number | null
  onBack: () => void
}) {
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [detail, setDetail] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (offline) {
      setLoading(false)
      return
    }
    loadOrders()
      .then((items) => {
        setOrders(items)
        if (focusOrderId) {
          return loadOrder(focusOrderId).then(setDetail)
        }
        return undefined
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить заказы'))
      .finally(() => setLoading(false))
  }, [offline, focusOrderId])

  const openOrder = (orderId: number) => {
    setError('')
    loadOrder(orderId).then(setDetail).catch((reason) => {
      setError(reason instanceof Error ? reason.message : 'Заказ не найден')
    })
  }

  return (
    <section className="page orders-page">
      <button className="back-link" onClick={onBack}><ArrowLeft size={18} /> Назад</button>
      <div className="page-title"><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Заказы</h1></div>
      {offline && <div className="form-error">Подключите backend, чтобы видеть историю заказов.</div>}
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted-line">Загружаем…</p>
      ) : detail ? (
        <article className="order-detail-card">
          <button className="text-button order-back-list" onClick={() => setDetail(null)}>← Все заказы</button>
          <div className="order-detail-head">
            <strong>Заказ №{detail.id}</strong>
            <span className={`status-pill status-${detail.status}`}>{detail.statusLabel}</span>
          </div>
          <small>{new Date(detail.createdAt).toLocaleString('ru-RU')}</small>
          <ul className="order-items">
            {detail.items.map((item) => (
              <li key={`${item.name}-${item.variant}`}>
                <span>{item.name} · {item.variant}</span>
                <span>{item.quantity} × {money.format(item.price)} ₽</span>
              </li>
            ))}
          </ul>
          <div className="order-detail-total"><span>Итого</span><strong>{money.format(detail.total)} ₽</strong></div>
        </article>
      ) : orders.length ? (
        <div className="order-list">
          {orders.map((order) => (
            <button className="order-list-item" key={order.id} onClick={() => openOrder(order.id)}>
              <div>
                <strong>№{order.id}</strong>
                <small>{new Date(order.createdAt).toLocaleDateString('ru-RU')} · {order.itemCount} поз.</small>
              </div>
              <div>
                <span className={`status-pill status-${order.status}`}>{order.statusLabel}</span>
                <strong>{money.format(order.total)} ₽</strong>
              </div>
            </button>
          ))}
        </div>
      ) : (
        !offline && <div className="empty-state"><strong>Пока нет заказов</strong><p>После подтверждения менеджер пришлёт кнопку «Открыть заказ».</p></div>
      )}
    </section>
  )
}

function AdminView({
  offline,
  onCatalogRefresh,
}: {
  offline: boolean
  onCatalogRefresh: () => Promise<void>
}) {
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState('')

  const refresh = () => {
    adminLoadOrders().then(setOrders).catch(() => setOrders([]))
  }

  useEffect(() => {
    if (!offline) refresh()
  }, [offline])

  const sync = async () => {
    setSyncing(true)
    setMessage('')
    try {
      const result = await adminSyncCatalog()
      await onCatalogRefresh()
      setMessage(`Синхронизировано: ${formatModelCount(result.products)}, уведомлений о поступлении: ${result.restocked}`)
      refresh()
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Ошибка синхронизации')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <section className="page admin-page">
      <div className="page-title"><h1>Админ</h1></div>
      <div className="admin-actions">
        <button className="primary-button" disabled={offline || syncing} onClick={sync}>
          <RefreshCw size={18} /> {syncing ? 'Синхронизация…' : 'Обновить из Google Sheets'}
        </button>
        <button className="text-button" disabled={offline} onClick={refresh}>Обновить список заказов</button>
      </div>
      {message && <p className="admin-message">{message}</p>}
      {offline && <div className="form-error">Админка доступна только при подключённом backend.</div>}
      <div className="admin-orders">
        <h2>Последние заказы</h2>
        {orders.map((order) => (
          <article className="admin-order-line" key={order.id}>
            <div className="admin-order-line__top">
              <div className="admin-order-line__id">
                <strong>№{order.id}</strong>
                <span className={`status-pill status-${order.status}`}>{order.statusLabel}</span>
              </div>
              <strong className="admin-order-line__total">{money.format(order.total)} ₽</strong>
            </div>
            <small className="admin-order-line__meta">
              {order.customerName || '—'} · {order.phone || '—'}
            </small>
          </article>
        ))}
        {!orders.length && !offline && (
          <p className="admin-orders-empty">Заказов пока нет</p>
        )}
      </div>
    </section>
  )
}

function BottomNav({
  view,
  cartCount,
  isAdmin,
  onHome,
  onCatalog,
  onCart,
  onAdmin,
  onSupport,
}: {
  view: View
  cartCount: number
  isAdmin: boolean
  onHome: () => void
  onCatalog: () => void
  onCart: () => void
  onAdmin: () => void
  onSupport: () => void
}) {
  return (
    <nav className="bottom-nav">
      <button className={view === 'home' ? 'is-active' : ''} onClick={onHome}><Home size={20} /><span>Главная</span></button>
      <button className={view === 'catalog' ? 'is-active' : ''} onClick={onCatalog}><LayoutGrid size={20} /><span>Каталог</span></button>
      <button className={view === 'cart' ? 'is-active' : ''} onClick={onCart}>
        <span className="nav-icon"><ShoppingBag size={20} />{cartCount > 0 && <i>{cartCount}</i>}</span><span>Корзина</span>
      </button>
      {isAdmin ? (
        <button className={view === 'admin' ? 'is-active' : ''} onClick={onAdmin}><Settings size={20} /><span>Админ</span></button>
      ) : (
        <button onClick={onSupport}><MessageCircle size={20} /><span>Написать</span></button>
      )}
    </nav>
  )
}

function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="loading-logo">CH</div>
      <strong>Готовим лёд</strong>
      <span><i /></span>
    </div>
  )
}

export default App
