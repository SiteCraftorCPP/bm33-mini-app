import { useEffect, useMemo, useState } from 'react'
import { Bell, Check, ChevronLeft, Minus, Plus, ShoppingBag, X } from 'lucide-react'
import { subscribeToRestock } from '../api'
import { pickVariantForFilters } from '../catalogFilters'
import { formatGripValue, sortGripSides } from '../gripLabel'
import type { Product, Variant } from '../types'
import { ProductVisual } from './ProductVisual'

const money = new Intl.NumberFormat('ru-RU')

const unique = (items: string[]) => [...new Set(items.filter(Boolean))]

type OptionPicks = {
  option1Value: string
  option2Value: string
  side: string
}

function picksFromVariant(variant: Variant | undefined): OptionPicks {
  if (!variant) {
    return { option1Value: '', option2Value: '', side: '' }
  }
  return {
    option1Value: variant.option1Value,
    option2Value: variant.option2Value,
    side: variant.side,
  }
}

export function resolveVariantByPicks(product: Product, picks: OptionPicks): Variant | undefined {
  return product.variants.find((variant) => {
    if (picks.option1Value && variant.option1Value !== picks.option1Value) return false
    if (picks.option2Value && variant.option2Value !== picks.option2Value) return false
    if (picks.side && variant.side !== picks.side) return false
    return true
  })
}

export function ProductSheet({
  product,
  preferredFilters,
  onClose,
  onAdd,
}: {
  product: Product | null
  preferredFilters?: Record<string, string>
  onClose: () => void
  onAdd: (product: Product, variant: Variant, quantity: number) => void
}) {
  const firstVariant = useMemo(() => {
    if (!product) return undefined
    if (preferredFilters && Object.values(preferredFilters).some(Boolean)) {
      return pickVariantForFilters(product, preferredFilters)
    }
    return product.variants.find((variant) => variant.stock > 0) ?? product.variants[0]
  }, [product, preferredFilters])
  const [picks, setPicks] = useState<OptionPicks>(() => picksFromVariant(firstVariant))
  const [quantity, setQuantity] = useState(1)
  const [subscribed, setSubscribed] = useState(false)

  const selected = useMemo(() => {
    if (!product) return undefined
    return resolveVariantByPicks(product, picks)
  }, [product, picks])

  useEffect(() => {
    setPicks(picksFromVariant(firstVariant))
    setQuantity(1)
    setSubscribed(false)
  }, [firstVariant, product])

  if (!product) return null

  const variantTemplate = product.variants[0]
  const option1Values = unique(product.variants.map((variant) => variant.option1Value))
  const option2Values = unique(product.variants.map((variant) => variant.option2Value))
  const sides = sortGripSides(unique(product.variants.map((variant) => variant.side)))

  const choose = (field: 'option1Value' | 'option2Value' | 'side', value: string) => {
    setPicks((current) => ({ ...current, [field]: value }))
    setQuantity(1)
  }

  const displayOptionValue = (field: 'option1Value' | 'option2Value' | 'side', value: string) =>
    field === 'side' ? formatGripValue(value) : value

  const optionGroup = (
    title: string,
    values: string[],
    field: 'option1Value' | 'option2Value' | 'side',
  ) =>
    values.length > 0 && (
      <div className="option-group">
        <div className="option-label">
          <span>{title}</span>
          <strong>{displayOptionValue(field, picks[field])}</strong>
        </div>
        <div className="option-pills">
          {values.map((value) => {
            const matchesOtherPicks = (variant: Variant) => {
              if (variant[field] !== value) return false
              if (field !== 'option1Value' && picks.option1Value && variant.option1Value !== picks.option1Value) {
                return false
              }
              if (field !== 'option2Value' && picks.option2Value && variant.option2Value !== picks.option2Value) {
                return false
              }
              if (field !== 'side' && picks.side && variant.side !== picks.side) return false
              return true
            }
            const available = product.variants.filter(matchesOtherPicks).some((variant) => variant.stock > 0)
            return (
              <button
                key={value}
                className={`${picks[field] === value ? 'is-selected' : ''} ${available ? '' : 'is-unavailable'}`}
                onClick={() => choose(field, value)}
              >
                {displayOptionValue(field, value)}
              </button>
            )
          })}
        </div>
      </div>
    )

  const subscribe = async () => {
    if (!selected) return
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
          <div className="sheet-price">{money.format(selected?.price ?? product.minPrice)} ₽</div>
          <p className="sheet-description">
            Профессиональная экипировка в наличии. Проверяем каждый товар перед отправкой.
          </p>

          {optionGroup(variantTemplate.option1Name || 'Вариант', option1Values, 'option1Value')}
          {optionGroup(variantTemplate.option2Name || 'Параметр', option2Values, 'option2Value')}
          {optionGroup('Хват', sides, 'side')}

          <div className={`availability-card ${selected?.stock ? '' : 'is-empty'}`}>
            <span>{selected?.stock ? <Check size={16} /> : <Bell size={16} />}</span>
            <div>
              <strong>
                {!selected
                  ? 'Нет такой комбинации'
                  : selected.stock
                    ? 'Можно заказывать'
                    : 'Сейчас нет в наличии'}
              </strong>
              <small>
                {!selected
                  ? 'Выберите другие параметры'
                  : selected.stock
                    ? `На складе ${selected.stock} шт.`
                    : 'Нажмите кнопку ниже — пришлём уведомление в Telegram, когда вариант снова будет в наличии'}
              </small>
            </div>
          </div>
        </div>

        <footer className="sheet-action">
          {selected && selected.stock > 0 ? (
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
          ) : selected ? (
            <button className="primary-button grow secondary" onClick={subscribe} disabled={subscribed}>
              {subscribed ? <Check size={18} /> : <Bell size={18} />}
              {subscribed ? 'Напишем в Telegram' : 'Сообщить в Telegram'}
            </button>
          ) : null}
        </footer>
      </section>
    </div>
  )
}
