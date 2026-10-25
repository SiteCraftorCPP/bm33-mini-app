import { categoryIconSrc } from './categoryIcons'

type Props = { category: string }

export function CategoryIcon({ category }: Props) {
  return (
    <span className="category-icon">
      <img src={categoryIconSrc(category)} alt="" width={28} height={28} decoding="async" />
    </span>
  )
}
