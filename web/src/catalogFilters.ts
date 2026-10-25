import type { CatalogFilterGroup, Product } from './types'

function sortValues(values: string[]) {
  const numeric = values.every((value) => /^-?\d+([.,]\d+)?$/.test(value))
  if (numeric) {
    return [...values].sort((a, b) => Number(a.replace(',', '.')) - Number(b.replace(',', '.')))
  }
  return [...values].sort((a, b) => a.localeCompare(b, 'ru'))
}

export function filterGroupsForCategory(category: string, products: Product[]): CatalogFilterGroup[] {
  if (category === 'Все') return []
  const variants = products.filter((product) => product.category === category).flatMap((product) => product.variants)
  if (!variants.length) return []

  const groups: CatalogFilterGroup[] = []
  const option1Name = variants.find((variant) => variant.option1Value)?.option1Name
  if (option1Name) {
    const values = sortValues([...new Set(variants.map((variant) => variant.option1Value).filter(Boolean))])
    if (values.length) groups.push({ key: 'option1', label: option1Name, values })
  }

  const option2Name = variants.find((variant) => variant.option2Value)?.option2Name
  if (option2Name) {
    const values = sortValues([...new Set(variants.map((variant) => variant.option2Value).filter(Boolean))])
    if (values.length) groups.push({ key: 'option2', label: option2Name, values })
  }

  const sides = sortValues([...new Set(variants.map((variant) => variant.side).filter(Boolean))])
  if (sides.length) {
    groups.push({ key: 'side', label: 'Сторона', values: sides })
  }

  return groups
}

export function productMatchesFilters(product: Product, filters: Record<string, string>) {
  const active = Object.entries(filters).filter(([, value]) => value)
  if (!active.length) return true
  return product.variants.some((variant) =>
    active.every(([key, value]) => {
      if (key === 'option1') return variant.option1Value === value
      if (key === 'option2') return variant.option2Value === value
      if (key === 'side') return variant.side === value
      return true
    }),
  )
}
