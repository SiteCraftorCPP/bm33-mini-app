import { describe, expect, it } from 'vitest'
import { formatGripValue, formatVariantLabel, sortGripSides } from './gripLabel'

describe('gripLabel', () => {
  it('maps L/R to Russian grip names', () => {
    expect(formatGripValue('L')).toBe('Левый')
    expect(formatGripValue('R')).toBe('Правый')
  })

  it('formats variant labels with grip', () => {
    expect(formatVariantLabel('70 / 92 / L')).toBe('70 / 92 / Левый')
  })

  it('puts left grip first', () => {
    expect(sortGripSides(['R', 'L'])).toEqual(['L', 'R'])
  })
})
