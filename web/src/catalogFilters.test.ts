import { describe, expect, it } from 'vitest'
import type { Product } from './types'
import {
  filterGroupsForCategory,
  pickVariantForFilters,
  productMatchesFilters,
  sanitizeCategoryFilters,
} from './catalogFilters'

const product: Product = {
  id: 'p1',
  name: 'Stick',
  category: 'Клюшки',
  description: '',
  imageUrl: '',
  stock: 1,
  minPrice: 1000,
  variants: [
    {
      id: 'a',
      option1Name: 'Флекс',
      option1Value: '20',
      option2Name: 'Загиб',
      option2Value: '92',
      side: 'L',
      label: '20 / 92 / L',
      stock: 2,
      price: 1000,
    },
    {
      id: 'b',
      option1Name: 'Флекс',
      option1Value: '30',
      option2Name: 'Загиб',
      option2Value: '28',
      side: 'L',
      label: '30 / 28 / L',
      stock: 0,
      price: 1000,
    },
    {
      id: 'c',
      option1Name: 'Флекс',
      option1Value: '30',
      option2Name: 'Загиб',
      option2Value: '92',
      side: 'L',
      label: '30 / 92 / L',
      stock: 1,
      price: 1000,
    },
  ],
}

describe('catalogFilters stock-aware', () => {
  it('hides out-of-stock flex values', () => {
    const groups = filterGroupsForCategory('Клюшки', [product], {})
    const flex = groups.find((group) => group.key === 'option1')
    expect(flex?.values).toEqual(['20', '30'])
  })

  it('narrows curve options when flex is selected', () => {
    const groups = filterGroupsForCategory('Клюшки', [product], { option1: '30' })
    const curve = groups.find((group) => group.key === 'option2')
    expect(curve?.values).toEqual(['92'])
  })

  it('does not list impossible triple filter combo', () => {
    const filters = { option1: '30', option2: '28', side: 'L' }
    expect(productMatchesFilters(product, filters)).toBe(false)
  })

  it('opens exact in-stock variant for active filters', () => {
    const filters = { option1: '30', option2: '92', side: 'L' }
    expect(pickVariantForFilters(product, filters)?.id).toBe('c')
  })

  it('drops invalid filter chips after cascade', () => {
    const sane = sanitizeCategoryFilters('Клюшки', [product], {
      option1: '30',
      option2: '28',
      side: 'L',
    })
    expect(sane.option2).toBe('')
  })
})
