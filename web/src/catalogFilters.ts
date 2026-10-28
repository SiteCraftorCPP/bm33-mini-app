import { formatGripValue } from './gripLabel'
import type { CatalogFilterGroup, Product, Variant } from './types'

export function formatFilterChipLabel(groupKey: string, value: string): string {
  if (groupKey === 'side') return formatGripValue(value)
  return value
}

function variantInStock(variant: Variant) {
  return variant.stock > 0
}

function variantMatchesSingleFilter(variant: Variant, key: string, value: string) {
  if (key === 'option1') return variant.option1Value === value
  if (key === 'option2') return variant.option2Value === value
  if (key === 'side') return variant.side === value
  return true
}

function variantMatchesFilters(variant: Variant, filters: Record<string, string>) {
  const active = Object.entries(filters).filter(([, value]) => value)
  if (!active.length) return true
  return active.every(([key, value]) => variantMatchesSingleFilter(variant, key, value))
}

function categoryVariants(products: Product[], category: string) {
  return products.filter((product) => product.category === category).flatMap((product) => product.variants)
}

function variantsForFilterOptions(
  products: Product[],
  category: string,
  filters: Record<string, string>,
  skipKey?: string,
) {
  return categoryVariants(products, category)
    .filter(variantInStock)
    .filter((variant) => {
      for (const [key, value] of Object.entries(filters)) {
        if (!value || key === skipKey) continue
        if (!variantMatchesSingleFilter(variant, key, value)) return false
      }
      return true
    })
}

function sortValues(values: string[]) {
  const numeric = values.every((value) => /^-?\d+([.,]\d+)?$/.test(value))
  if (numeric) {
    return [...values].sort((a, b) => Number(a.replace(',', '.')) - Number(b.replace(',', '.')))
  }
  return [...values].sort((a, b) => a.localeCompare(b, 'ru'))
}

export function filterGroupsForCategory(
  category: string,
  products: Product[],
  activeFilters: Record<string, string> = {},
): CatalogFilterGroup[] {
  if (category === 'Все') return []

  const groups: CatalogFilterGroup[] = []
  const option1Pool = variantsForFilterOptions(products, category, activeFilters, 'option1')
  const option1Name = option1Pool.find((variant) => variant.option1Value)?.option1Name
  if (option1Name) {
    const values = sortValues([...new Set(option1Pool.map((variant) => variant.option1Value).filter(Boolean))])
    if (values.length) groups.push({ key: 'option1', label: option1Name, values })
  }

  const option2Pool = variantsForFilterOptions(products, category, activeFilters, 'option2')
  const option2Name = option2Pool.find((variant) => variant.option2Value)?.option2Name
  if (option2Name) {
    const values = sortValues([...new Set(option2Pool.map((variant) => variant.option2Value).filter(Boolean))])
    if (values.length) groups.push({ key: 'option2', label: option2Name, values })
  }

  const sidePool = variantsForFilterOptions(products, category, activeFilters, 'side')
  const sides = sortValues([...new Set(sidePool.map((variant) => variant.side).filter(Boolean))])
  if (sides.length) {
    groups.push({ key: 'side', label: 'Хват', values: sides })
  }

  return groups
}

export function sanitizeCategoryFilters(
  category: string,
  products: Product[],
  filters: Record<string, string>,
): Record<string, string> {
  if (category === 'Все') return {}
  let next = { ...filters }
  let changed = true
  while (changed) {
    changed = false
    for (const group of filterGroupsForCategory(category, products, next)) {
      const value = next[group.key]
      if (value && !group.values.includes(value)) {
        next = { ...next, [group.key]: '' }
        changed = true
      }
    }
  }
  return next
}

export function pickVariantForFilters(product: Product, filters: Record<string, string>): Variant | undefined {
  const active = Object.entries(filters).filter(([, value]) => value)
  const inStock = product.variants.filter(variantInStock)
  if (!active.length) {
    return inStock[0] ?? product.variants[0]
  }
  const matching = inStock.filter((variant) => variantMatchesFilters(variant, filters))
  if (matching.length) return matching[0]
  const requested = product.variants.filter((variant) => variantMatchesFilters(variant, filters))
  return requested[0]
}

export function productMatchesFilters(product: Product, filters: Record<string, string>) {
  const active = Object.entries(filters).filter(([, value]) => value)
  if (!active.length) return true
  return product.variants.some(
    (variant) => variantInStock(variant) && variantMatchesFilters(variant, filters),
  )
}
