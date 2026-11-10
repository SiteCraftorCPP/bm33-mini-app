export function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (!digits) {
    throw new Error('Укажите номер телефона')
  }
  let next = digits
  if (next.length === 10) {
    if (next[0] === '8') {
      throw new Error('Не хватает цифр — укажите полный номер (+7 и 10 цифр)')
    }
    if (next[0] === '9') {
      next = `7${next}`
    } else {
      throw new Error('Нужен российский номер (+7 …)')
    }
  } else if (next.length === 11 && next[0] === '8') {
    next = `7${next.slice(1)}`
  }
  if (next.length !== 11 || next[0] !== '7' || next[1] !== '9') {
    throw new Error('Нужен полный мобильный +7 9XX XXX XX XX')
  }
  return `+${next}`
}

export function formatPhoneInput(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 11)
  if (!digits) return ''
  let body = digits
  if (body[0] === '8') body = `7${body.slice(1)}`
  if (body[0] !== '7') body = `7${body.slice(0, 10)}`
  const d = body.padEnd(11, '_').slice(0, 11)
  return `+${d[0]} ${d.slice(1, 4)} ${d.slice(4, 7)} ${d.slice(7, 9)} ${d.slice(9, 11)}`.replace(/_/g, '').trim()
}
