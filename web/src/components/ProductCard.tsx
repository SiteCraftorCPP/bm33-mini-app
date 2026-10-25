import { ArrowUpRight } from 'lucide-react'
import type { Product } from '../types'
import { ProductVisual } from './ProductVisual'

const money = new Intl.NumberFormat('ru-RU')

export function ProductCard({
  product,
  onOpen,
}: {
  product: Product
  onOpen: (product: Product) => void
}) {
  return (
    <button className="product-card" onClick={() => onOpen(product)} aria-label={`Открыть ${product.name}`}>
      <div className="card-image-wrap">
        <ProductVisual category={product.category} imageUrl={product.imageUrl} />
        <span className={`stock-pill ${product.stock ? '' : 'is-empty'}`}>
          {product.stock ? `В наличии · ${product.stock}` : 'Под заказ'}
        </span>
      </div>
      <div className="product-card-body">
        <span className="eyebrow">{product.category}</span>
        <strong>{product.name.replace(/\s[LR](?=\s|$)/, '')}</strong>
        <div className="product-price-row">
          <span>от {money.format(product.minPrice)} ₽</span>
          <span className="round-arrow"><ArrowUpRight size={17} /></span>
        </div>
      </div>
    </button>
  )
}
