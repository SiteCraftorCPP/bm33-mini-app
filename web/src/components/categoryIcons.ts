/** Готовые SVG с Iconify (MDI / Game Icons), лежат в public/categories */
export const CATEGORY_ICON_SRC: Record<string, string> = {
  Клюшки: '/categories/sticks.svg',
  Вратарские: '/categories/goalie.svg',
  Коньки: '/categories/skates.svg',
  'Термобельё': '/categories/baselayer.svg',
  Перчатки: '/categories/gloves.svg',
  'Защита и одежда': '/categories/protection.svg',
  'Баулы и рюкзаки': '/categories/bags.svg',
}

export function categoryIconSrc(name: string): string {
  return CATEGORY_ICON_SRC[name] ?? CATEGORY_ICON_SRC['Клюшки']
}
