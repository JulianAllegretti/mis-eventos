import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { EventCard } from '@/features/events/EventCard'
import { makeEvent } from '@/test/factories'

const renderCard = (overrides = {}) =>
  render(
    <MemoryRouter>
      <EventCard
        event={makeEvent({ name: 'Congreso de Python', location: 'Medellín', ...overrides })}
      />
    </MemoryRouter>,
  )

describe('EventCard', () => {
  it('muestra nombre, lugar y estado, y enlaza al detalle', () => {
    renderCard({ id: 'abc' })

    expect(screen.getByRole('link', { name: 'Congreso de Python' })).toHaveAttribute(
      'href',
      '/events/abc',
    )
    expect(screen.getByText('Medellín')).toBeInTheDocument()
    expect(screen.getByText('Publicado')).toBeInTheDocument()
  })

  it('informa los cupos disponibles', () => {
    renderCard({ capacity: 40, registered_count: 10, available_slots: 30 })
    expect(screen.getByText('30 de 40 cupos disponibles')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: '10 de 40 cupos ocupados' })).toBeInTheDocument()
  })

  it('avisa cuando está agotado', () => {
    renderCard({ capacity: 5, registered_count: 5, available_slots: 0 })
    expect(screen.getByText('Sin cupos disponibles')).toBeInTheDocument()
  })

  it.each([
    ['draft', 'Borrador'],
    ['finished', 'Finalizado'],
    ['cancelled', 'Cancelado'],
  ] as const)('traduce el estado %s', (status, label) => {
    renderCard({ status })
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
