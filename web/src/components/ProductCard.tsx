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
      </div>
      <div className="product-card-body">
        <div className="product-card-meta">
          <span className="eyebrow">{product.category}</span>
          <span className={`stock-badge ${product.stock ? 'is-in-stock' : 'is-order'}`}>
            {product.stock ? `В наличии · ${product.stock}` : 'Под заказ'}
          </span>
        </div>
        <strong>{product.name.replace(/\s[LR](?=\s|$)/, '')}</strong>
        <div className="product-price-row">
          <span>от {money.format(product.minPrice)} ₽</span>
          <span className="round-arrow"><ArrowUpRight size={17} /></span>
        </div>
      </div>
    </button>
  )
}
