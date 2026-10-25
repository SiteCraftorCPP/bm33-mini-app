import { useEffect, useMemo, useState } from 'react'
import { Bell, Check, ChevronLeft, Minus, Plus, ShoppingBag, X } from 'lucide-react'
import { subscribeToRestock } from '../api'
import type { Product, Variant } from '../types'
import { ProductVisual } from './ProductVisual'

const money = new Intl.NumberFormat('ru-RU')

const unique = (items: string[]) => [...new Set(items.filter(Boolean))]

export function ProductSheet({
  product,
  onClose,
  onAdd,
}: {
  product: Product | null
  onClose: () => void
  onAdd: (product: Product, variant: Variant, quantity: number) => void
}) {
  const firstVariant = useMemo(
    () => product?.variants.find((variant) => variant.stock > 0) ?? product?.variants[0],
    [product],
  )
  const [selected, setSelected] = useState<Variant | undefined>(firstVariant)
  const [quantity, setQuantity] = useState(1)
  const [subscribed, setSubscribed] = useState(false)

  useEffect(() => {
    setSelected(firstVariant)
    setQuantity(1)
    setSubscribed(false)
  }, [firstVariant, product])

  if (!product || !selected) return null

  const option1Values = unique(product.variants.map((variant) => variant.option1Value))
  const option2Values = unique(product.variants.map((variant) => variant.option2Value))
  const sides = unique(product.variants.map((variant) => variant.side))

  const choose = (field: 'option1Value' | 'option2Value' | 'side', value: string) => {
    const exact = product.variants.find(
      (variant) =>
        variant[field] === value &&
        (field === 'option1Value' || !selected.option1Value || variant.option1Value === selected.option1Value) &&
        (field === 'option2Value' || !selected.option2Value || variant.option2Value === selected.option2Value) &&
        (field === 'side' || !selected.side || variant.side === selected.side),
    )
    setSelected(exact ?? product.variants.find((variant) => variant[field] === value) ?? selected)
    setQuantity(1)
  }

  const optionGroup = (
    title: string,
    values: string[],
    field: 'option1Value' | 'option2Value' | 'side',
  ) =>
    values.length > 0 && (
      <div className="option-group">
        <div className="option-label">
          <span>{title}</span>
          <strong>{selected[field]}</strong>
        </div>
        <div className="option-pills">
          {values.map((value) => {
            const candidates = product.variants.filter((variant) => variant[field] === value)
            const available = candidates.some((variant) => variant.stock > 0)
            return (
              <button
                key={value}
                className={`${selected[field] === value ? 'is-selected' : ''} ${available ? '' : 'is-unavailable'}`}
                onClick={() => choose(field, value)}
              >
                {value}
              </button>
            )
          })}
        </div>
      </div>
    )

  const subscribe = async () => {
    try {
      await subscribeToRestock(selected.id)
      setSubscribed(true)
      window.Telegram?.WebApp.HapticFeedback?.notificationOccurred('success')
    } catch {
      setSubscribed(true)
    }
  }

  return (
    <div className="sheet-backdrop" onMouseDown={onClose}>
      <section className="product-sheet" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-visual">
          <ProductVisual category={product.category} imageUrl={product.imageUrl} />
          <button className="sheet-back" onClick={onClose} aria-label="Закрыть">
            <ChevronLeft size={22} />
          </button>
          <button className="sheet-close" onClick={onClose} aria-label="Закрыть">
            <X size={19} />
          </button>
          <span className="sheet-number">CH / {product.id.slice(-3).toUpperCase()}</span>
        </div>

        <div className="sheet-content">
          <span className="eyebrow">{product.category}</span>
          <h2>{product.name.replace(/\s[LR](?=\s|$)/, '')}</h2>
          <div className="sheet-price">{money.format(selected.price)} ₽</div>
          <p className="sheet-description">
            Профессиональная экипировка в наличии. Проверяем каждый товар перед отправкой.
          </p>

          {optionGroup(selected.option1Name || 'Вариант', option1Values, 'option1Value')}
          {optionGroup(selected.option2Name || 'Параметр', option2Values, 'option2Value')}
          {optionGroup('Сторона', sides, 'side')}

          <div className={`availability-card ${selected.stock ? '' : 'is-empty'}`}>
            <span>{selected.stock ? <Check size={16} /> : <Bell size={16} />}</span>
            <div>
              <strong>{selected.stock ? 'Можно заказывать' : 'Сейчас нет в наличии'}</strong>
              <small>
                {selected.stock
                  ? `На складе ${selected.stock} шт.`
                  : 'Нажмите кнопку ниже — пришлём уведомление в Telegram, когда вариант снова будет в наличии'}
              </small>
            </div>
          </div>
        </div>

        <footer className="sheet-action">
          {selected.stock > 0 ? (
            <>
              <div className="qty-control">
                <button aria-label="Уменьшить количество" onClick={() => setQuantity(Math.max(1, quantity - 1))}><Minus size={16} /></button>
                <span>{quantity}</span>
                <button aria-label="Увеличить количество" onClick={() => setQuantity(Math.min(selected.stock, quantity + 1))}><Plus size={16} /></button>
              </div>
              <button
                className="primary-button grow"
                onClick={() => {
                  onAdd(product, selected, quantity)
                  onClose()
                }}
              >
                <ShoppingBag size={18} /> В корзину
              </button>
            </>
          ) : (
            <button className="primary-button grow secondary" onClick={subscribe} disabled={subscribed}>
              {subscribed ? <Check size={18} /> : <Bell size={18} />}
              {subscribed ? 'Напишем в Telegram' : 'Сообщить в Telegram'}
            </button>
          )}
        </footer>
      </section>
    </div>
  )
}
