/** Format hiển thị — dùng locale vi-VN cho ngày, USD cho tiền (IEEE-CIS là USD). */

const currency = new Intl.NumberFormat('vi-VN', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatAmount(value: number): string {
  return currency.format(value)
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : dateTime.format(d)
}

export function formatProbability(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

/** SHAP value luôn hiện dấu — để không phụ thuộc vào màu (a11y). */
export function formatSigned(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toFixed(3)}`
}

export function formatFeatureValue(value: string | number | null): string {
  if (value === null) return '—'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(4)
  }
  return value === '__MISSING__' ? 'thiếu dữ liệu' : value
}
