import {
  formatDateTime,
  formatRange,
  formatTime,
  fromDatetimeLocal,
  toDatetimeLocal,
} from '@/utils/date'

describe('fechas', () => {
  it('convierte entre ISO y datetime-local sin perder el instante', () => {
    const iso = '2030-05-10T14:30:00.000Z'
    const local = toDatetimeLocal(iso)
    expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(fromDatetimeLocal(local)).toBe(iso)
  })

  it('fromDatetimeLocal devuelve ISO en UTC con zona horaria (lo que exige el backend)', () => {
    expect(fromDatetimeLocal('2030-05-10T09:00')).toMatch(/Z$/)
  })

  it('formatRange resume el mismo día con una sola fecha', () => {
    const range = formatRange('2030-05-10T14:00:00Z', '2030-05-10T16:00:00Z')
    expect(range.match(/2030/g)).toHaveLength(1)
    expect(range).toContain('–')
  })

  it('formatRange muestra ambas fechas si el evento dura varios días', () => {
    const range = formatRange('2030-05-10T14:00:00Z', '2030-05-12T16:00:00Z')
    expect(range.match(/2030/g)).toHaveLength(2)
  })

  it('nunca separa «a. m.» / «p. m.» entre dos líneas', () => {
    const texts = [
      formatTime('2030-05-10T09:00:00-05:00'),
      formatTime('2030-05-10T21:00:00-05:00'),
      formatDateTime('2030-05-10T21:00:00-05:00'),
      formatRange('2030-05-10T09:00:00-05:00', '2030-05-10T21:00:00-05:00'),
    ]
    for (const text of texts) {
      expect(text).not.toMatch(/[ap]\. m\./) // sin espacio normal entre «a.» y «m.»
      expect(text).not.toMatch(/\d [ap]\./) // ni entre la hora y «a.»/«p.»
    }
  })
})
