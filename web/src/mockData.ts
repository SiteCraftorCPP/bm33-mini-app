import type { Catalog, Product } from './types'

const makeProduct = (
  id: string,
  name: string,
  category: string,
  price: number,
  variants: Array<[string, string, string, string, number]>,
): Product => ({
  id,
  name,
  category,
  description: '',
  imageUrl: '',
  minPrice: price,
  stock: variants.reduce((sum, item) => sum + item[4], 0),
  variants: variants.map(([first, second, side, suffix, stock], index) => ({
    id: `${id}-${index}`,
    option1Name: category === 'Клюшки' ? 'Флекс' : 'Размер',
    option1Value: first,
    option2Name: category === 'Клюшки' ? 'Загиб' : suffix ? 'Цвет' : '',
    option2Value: second,
    side,
    label: [first, second, side].filter(Boolean).join(' / '),
    stock,
    price,
  })),
})

export const mockCatalog: Catalog = {
  categories: [
    'Клюшки',
    'Вратарские',
    'Коньки',
    'Термобельё',
    'Перчатки',
    'Защита и одежда',
    'Баулы и рюкзаки',
  ].map((name) => ({ id: name, name, count: 1 })),
  products: [
    makeProduct('fuse', 'Bauer Fuse', 'Клюшки', 7500, [
      ['70', 'P92', 'L', '', 12],
      ['77', 'P28', 'L', '', 0],
      ['70', 'P28', 'R', '', 6],
      ['87', 'P92', 'R', '', 0],
    ]),
    makeProduct('ft9', 'CCM Jetspeed FT9 Pro', 'Клюшки', 7500, [
      ['65', 'P29', 'L', '', 7],
      ['70', 'P28', 'L', '', 16],
      ['75', 'P29', 'R', '', 0],
    ]),
    makeProduct('flylite', 'Bauer Flylite', 'Вратарские', 10500, [
      ['27', 'P31', 'L', '', 2],
      ['25', 'P31', 'R', '', 0],
    ]),
    makeProduct('shadow', 'Bauer Shadow', 'Коньки', 30000, [
      ['8.0', 'Fit 2', '', '', 1],
      ['9.0', 'Fit 3', '', '', 3],
    ]),
    makeProduct('base', 'Термобельё CCM SR', 'Термобельё', 4500, [
      ['M', '', '', '', 18],
      ['L', '', '', '', 14],
    ]),
    makeProduct('gloves', 'Перчатки CCM FT8 Pro', 'Перчатки', 6500, [
      ['13', 'Тёмно-синие', '', 'Цвет', 1],
      ['12', 'Синие', '', 'Цвет', 7],
    ]),
    makeProduct('chest', 'Нагрудник Bauer Hyperlite', 'Защита и одежда', 9000, [
      ['M', '', '', '', 2],
      ['L', '', '', '', 4],
    ]),
    makeProduct('bag', 'Баул Winloot', 'Баулы и рюкзаки', 9500, [
      ['INT', '', '', '', 2],
      ['SR', '', '', '', 3],
    ]),
  ],
}
