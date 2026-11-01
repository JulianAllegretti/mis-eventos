import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from '@/components/ConfirmDialog'

function setup(onConfirm = vi.fn()) {
  const onOpenChange = vi.fn()
  render(
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title="Cancelar evento"
      description="Esta acción no se puede deshacer."
      confirmLabel="Sí, cancelar"
      destructive
      onConfirm={onConfirm}
    />,
  )
  return { onConfirm, onOpenChange }
}

describe('ConfirmDialog', () => {
  it('muestra el título y la descripción', () => {
    setup()
    expect(screen.getByRole('dialog', { name: 'Cancelar evento' })).toBeInTheDocument()
    expect(screen.getByText('Esta acción no se puede deshacer.')).toBeInTheDocument()
  })

  it('al confirmar ejecuta la acción y se cierra', async () => {
    const { onConfirm, onOpenChange } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar' }))

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('"Volver" cierra sin ejecutar la acción', async () => {
    const { onConfirm, onOpenChange } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Volver' }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('bloquea los botones mientras la acción está en curso', async () => {
    let finish!: () => void
    const pending = new Promise<void>((resolve) => (finish = resolve))
    setup(vi.fn(() => pending))

    await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar' }))

    expect(screen.getByRole('button', { name: /sí, cancelar/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Volver' })).toBeDisabled()
    finish()
  })
})
