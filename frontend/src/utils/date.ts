const LOCALE = 'es-CO'

const dateFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium' })
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeStyle: 'short' })
const timeFormat = new Intl.DateTimeFormat(LOCALE, { timeStyle: 'short' })

/** Une la hora con «a. m.» / «p. m.» usando espacios duros, para que nunca se parta entre líneas. */
const keepMeridiem = (text: string) =>
  text.replace(/(\d)\s?([ap])\.\s?m\./gi, '$1\u00a0$2.\u00a0m.')

export const formatDate = (iso: string) => dateFormat.format(new Date(iso))
export const formatDateTime = (iso: string) => keepMeridiem(dateTimeFormat.format(new Date(iso)))
export const formatTime = (iso: string) => keepMeridiem(timeFormat.format(new Date(iso)))

function sameDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString()
}

/** "1 nov 2026, 9:00 a. m. – 5:00 p. m." si es el mismo día; si no, ambas fechas completas. */
export function formatRange(startIso: string, endIso: string) {
  const start = new Date(startIso)
  const end = new Date(endIso)
  const from = keepMeridiem(dateTimeFormat.format(start))
  if (sameDay(start, end)) return `${from} – ${keepMeridiem(timeFormat.format(end))}`
  return `${from} – ${keepMeridiem(dateTimeFormat.format(end))}`
}

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO → valor de `<input type="datetime-local">` en la zona horaria del navegador. */
export function toDatetimeLocal(iso: string) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Valor de `<input type="datetime-local">` → ISO en UTC (el backend exige zona horaria). */
export function fromDatetimeLocal(value: string) {
  return new Date(value).toISOString()
}
