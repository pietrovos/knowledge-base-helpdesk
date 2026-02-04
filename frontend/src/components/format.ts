export function timeAgo(iso: string, now = Date.now()) {
  const s = Math.round((now - new Date(iso).getTime()) / 1000)
  if (s < 45) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  return d < 30 ? `${d}d ago` : new Date(iso).toLocaleDateString()
}

export function bytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** "Refund Policy > Exceptions" under the document "Refund Policy" displays as "Exceptions". */
export function sectionLabel(documentTitle: string, heading: string) {
  const parts = heading.split(' > ')
  if (parts[0]?.trim().toLowerCase() === documentTitle.trim().toLowerCase()) parts.shift()
  return parts.join(' › ')
}
