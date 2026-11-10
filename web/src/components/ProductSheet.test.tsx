import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Product } from '../types'
import { ProductSheet } from './ProductSheet'

const product: Product = {
  id: 'fuse',
  name: 'Bauer Fuse',
  category: 'Клюшки',
  description: '',
  imageUrl: '',
  stock: 2,
  minPrice: 7500,
  variants: [
    {
      id: 'available',
      option1Name: 'Флекс',
      option1Value: '70',
      option2Name: 'Загиб',
      option2Value: '92',
      side: 'L',
      label: '70 / 92 / L',
      stock: 2,
      price: 7500,
    },
    {
      id: 'empty',
      option1Name: 'Флекс',
      option1Value: '77',
      option2Name: 'Загиб',
      option2Value: '28',
      side: 'R',
      label: '77 / 28 / R',
      stock: 0,
      price: 7500,
    },
  ],
}

describe('ProductSheet', () => {
  it('adds no more than the available stock', () => {
    const onAdd = vi.fn()
    render(<ProductSheet product={product} onClose={vi.fn()} onAdd={onAdd} />)

    fireEvent.click(screen.getByLabelText('Увеличить количество'))
    fireEvent.click(screen.getByLabelText('Увеличить количество'))
    fireEvent.click(screen.getByText('В корзину'))

    expect(onAdd).toHaveBeenCalledWith(product, product.variants[0], expect.any(Number))
    expect(onAdd.mock.calls[0][2]).toBe(2)
  })

  it('keeps size when color has no matching variant', () => {
    const sizedProduct: Product = {
      ...product,
      variants: [
        {
          ...product.variants[0],
          id: 'w11',
          option1Name: 'Размер',
          option1Value: '11',
          option2Name: 'Цвет',
          option2Value: 'белый',
          label: '11 / белый',
        },
        {
          ...product.variants[0],
          id: 'b12',
          option1Name: 'Размер',
          option1Value: '12',
          option2Name: 'Цвет',
          option2Value: 'чёрный',
          label: '12 / чёрный',
        },
      ],
    }
    render(<ProductSheet product={sizedProduct} onClose={vi.fn()} onAdd={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '11' }))
    fireEvent.click(screen.getByRole('button', { name: 'чёрный' }))

    expect(screen.getByRole('button', { name: '11' })).toHaveClass('is-selected')
    expect(screen.getByText('Нет такой комбинации')).toBeInTheDocument()
  })

  it('shows restock action for an unavailable variant', () => {
    render(<ProductSheet product={{ ...product, variants: [product.variants[1]], stock: 0 }} onClose={vi.fn()} onAdd={vi.fn()} />)

    expect(screen.getByText('Хват')).toBeInTheDocument()
    expect(screen.getByText('Сообщить в Telegram')).toBeInTheDocument()
    expect(screen.queryByText('В корзину')).not.toBeInTheDocument()
  })
})
