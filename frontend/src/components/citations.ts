const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g

export type Segment = { kind: 'text'; text: string } | { kind: 'cite'; chunkId: number }

/** Split a reply into text and citation segments. */
export function parseCitations(text: string): Segment[] {
  const out: Segment[] = []
  let last = 0
  for (const m of text.matchAll(MARKER)) {
    if (m.index > last) out.push({ kind: 'text', text: text.slice(last, m.index) })
    for (const id of m[1].split(',')) out.push({ kind: 'cite', chunkId: Number(id.trim()) })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ kind: 'text', text: text.slice(last) })
  return out
}

/** What the customer receives: no internal chunk references. Mirrors the server's strip_markers. */
export function stripCitations(text: string) {
  return text
    .replace(MARKER, '')
    .replace(/[ \t]+([.,;:!?])/g, '$1')
    .split('\n')
    .map((l) => l.replace(/[ \t]{2,}/g, ' ').trimEnd())
    .join('\n')
    .trim()
}
