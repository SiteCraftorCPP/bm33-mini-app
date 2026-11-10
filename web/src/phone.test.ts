import { describe, expect, it } from 'vitest'
import { normalizePhone } from './phone'

describe('normalizePhone', () => {
  it('accepts 10 digits', () => {
    expect(normalizePhone('9991234567')).toBe('+79991234567')
  })

  it('accepts 11 digits starting with 8', () => {
    expect(normalizePhone('89991234567')).toBe('+79991234567')
  })

  it('rejects short numbers', () => {
    expect(() => normalizePhone('8927784060')).toThrow()
  })
})
