import { useState } from 'react'

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
  const [failed, setFailed] = useState(false)
  const showPhoto = Boolean(imageUrl) && !failed

  return (
    <div
      className={`product-visual tone-${tone % 7} ${compact ? 'is-compact' : ''} ${showPhoto ? 'has-photo' : ''}`}
    >
      {showPhoto ? (
        <img
          className="product-photo"
          src={imageUrl}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <img className="product-category-icon" src={categoryIconSrc(category)} alt="" />
      )}
      {!showPhoto && (
        <>
          <span className="visual-glow" />
          <span className="visual-line" />
        </>
      )}
    </div>
  )
}
