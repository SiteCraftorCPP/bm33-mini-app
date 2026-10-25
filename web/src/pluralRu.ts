/** Склонение «модель» для русского: 1 модель, 2 модели, 5 моделей, 21 модель… */
export function formatModelCount(count: number): string {
  const n = Math.abs(Math.trunc(count))
  const mod10 = n % 10
  const mod100 = n % 100
  let word = 'моделей'
  if (mod10 === 1 && mod100 !== 11) word = 'модель'
  else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) word = 'модели'
  return `${count} ${word}`
}
