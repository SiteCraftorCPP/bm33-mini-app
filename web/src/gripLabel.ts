const GRIP_LABELS: Record<string, string> = {
  L: 'Левый',
  R: 'Правый',
  l: 'Левый',
  r: 'Правый',
}

export function formatGripValue(side: string): string {
  const trimmed = side.trim()
  return GRIP_LABELS[trimmed] ?? trimmed
}

/** Хват: слева «Левый», справа «Правый». */
export function sortGripSides(sides: string[]): string[] {
  const rank = (side: string) => {
    const key = side.trim().toUpperCase()
    if (key === 'L' || key.startsWith('ЛЕВ')) return 0
    if (key === 'R' || key.startsWith('ПРАВ')) return 1
    return 2
  }
  return [...sides].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, 'ru'))
}

/** Показ варианта в корзине и заказах: L/R → Левый/Правый */
export function formatVariantLabel(label: string): string {
  return label
    .split(' / ')
    .map((part) => {
      const key = part.trim()
      return GRIP_LABELS[key] ?? part
    })
    .join(' / ')
}
