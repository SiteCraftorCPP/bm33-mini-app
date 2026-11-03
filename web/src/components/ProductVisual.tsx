import { useEffect, useState } from 'react'

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
  const [photoState, setPhotoState] = useState<'idle' | 'loading' | 'ready' | 'failed'>('idle')

  useEffect(() => {
    setPhotoState(imageUrl ? 'loading' : 'idle')
  }, [imageUrl])

  const showPhoto = photoState === 'ready'
  const pendingPhoto = photoState === 'loading'

  return (
    <div
      className={`product-visual tone-${tone % 7} ${compact ? 'is-compact' : ''} ${showPhoto || pendingPhoto ? 'has-photo' : ''} ${pendingPhoto ? 'is-photo-pending' : ''}`}
    >
      {imageUrl && photoState !== 'failed' ? (
        <img
          className={`product-photo ${showPhoto ? 'is-visible' : 'is-preload'}`}
          src={imageUrl}
          alt=""
          loading="lazy"
          decoding="async"
          onLoad={() => setPhotoState('ready')}
          onError={() => setPhotoState('failed')}
        />
      ) : null}
      {!showPhoto && !pendingPhoto ? (
        <img className="product-category-icon" src={categoryIconSrc(category)} alt="" />
      ) : null}
      {!showPhoto && !pendingPhoto && (
        <>
          <span className="visual-glow" />
          <span className="visual-line" />
        </>
      )}
    </div>
  )
}
