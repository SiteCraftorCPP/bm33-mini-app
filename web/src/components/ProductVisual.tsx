import { CATEGORY_ICON_SRC, categoryIconSrc } from './categoryIcons'

export function ProductVisual({
  category,
  imageUrl,
  compact = false,
}: {
  category: string
  imageUrl?: string
  compact?: boolean
}) {
  const tone = Object.keys(CATEGORY_ICON_SRC).indexOf(category)

  return (
    <div className={`product-visual tone-${tone % 7} ${compact ? 'is-compact' : ''}`}>
      {imageUrl ? (
        <img src={imageUrl} alt="" />
      ) : (
        <img className="product-category-icon" src={categoryIconSrc(category)} alt="" />
      )}
      <span className="visual-glow" />
      <span className="visual-line" />
    </div>
  )
}
