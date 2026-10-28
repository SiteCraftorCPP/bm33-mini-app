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
