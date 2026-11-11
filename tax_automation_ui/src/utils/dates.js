const pad = (n) => String(n).padStart(2, '0')

/** Local YYYY-MM-DD (toISOString would shift the day in India). */
export const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const todayStr = () => iso(new Date())

/** First 10 chars of a date or datetime string, or ''. */
export const day = (v) => (v ? String(v).slice(0, 10) : '')

const parse = (v) => {
  const [y, m, d] = day(v).split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Whole days from today (negative = past). */
export const daysFromToday = (v) => {
  const t = new Date()
  return Math.round((parse(v) - new Date(t.getFullYear(), t.getMonth(), t.getDate())) / 86400000)
}

export const fmtDate = (v, opts = { day: 'numeric', month: 'short' }) =>
  day(v) ? parse(v).toLocaleDateString('en-IN', opts) : '—'