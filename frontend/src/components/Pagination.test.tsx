import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Pagination } from '@/components/Pagination'

describe('Pagination', () => {
  it('no se muestra si todo cabe en una página', () => {
    const { container } = render(
      <Pagination page={1} pageSize={9} total={9} onPageChange={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra la página actual y navega', async () => {
    const onPageChange = vi.fn()
    render(<Pagination page={2} pageSize={9} total={30} onPageChange={onPageChange} />)

    expect(screen.getByText('Página 2 de 4')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /siguiente/i }))
    await userEvent.click(screen.getByRole('button', { name: /anterior/i }))

    expect(onPageChange).toHaveBeenNthCalledWith(1, 3)
    expect(onPageChange).toHaveBeenNthCalledWith(2, 1)
  })

  it('deshabilita "Anterior" en la primera y "Siguiente" en la última', () => {
    const { rerender } = render(
      <Pagination page={1} pageSize={9} total={20} onPageChange={() => {}} />,
    )
    expect(screen.getByRole('button', { name: /anterior/i })).toBeDisabled()

    rerender(<Pagination page={3} pageSize={9} total={20} onPageChange={() => {}} />)
    expect(screen.getByRole('button', { name: /siguiente/i })).toBeDisabled()
  })
})
