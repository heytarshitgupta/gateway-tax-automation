const IST_DATE_FMT = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Kolkata',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** Business date YYYY-MM-DD in IST (Asia/Kolkata), independent of browser timezone. */
export const iso = (d = new Date()) => IST_DATE_FMT.format(d)
export const todayStr = () => iso(new Date())

/** First 10 chars of a date or datetime string, or ''. */
export const day = (v) => (v ? String(v).slice(0, 10) : '')

const parse = (v) => {
  const [y, m, d] = day(v).split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Whole calendar days from IST today (negative = past). Used for DATE-only compliance_dates. */
export const daysFromToday = (v) => {
  return Math.round((parse(v) - parse(todayStr())) / 86400000)
}

export const fmtDate = (v, opts = { day: 'numeric', month: 'short' }) =>
  day(v) ? parse(v).toLocaleDateString('en-IN', opts) : '—'

/** Interprets naive DB timestamps as UTC and formats them in IST (Asia/Kolkata). */
export const formatIstTimestamp = (ts) => {
  if (!ts) return '—'
  try {
    const raw = String(ts).trim()
    const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
    const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(normalized)
    const d = new Date(hasTz ? normalized : `${normalized}Z`)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
  } catch {
    return ts
  }
}
