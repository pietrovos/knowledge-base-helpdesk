export interface TipRow {
  color: string
  label: string
  value: string
}

/** Values lead, labels follow; series keyed with a short line in the series color. */
export function Tooltip({ x, y, title, rows, width }: { x: number; y: number; title: string; rows: TipRow[]; width: number }) {
  const left = Math.min(Math.max(x + 12, 0), width - 170)
  return (
    <div role="tooltip" className="pointer-events-none absolute z-10 w-40 rounded-md bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-black/10" style={{ left, top: Math.max(0, y - 8) }}>
      <p className="mb-1 text-[var(--viz-ink-2)]">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3 rounded" style={{ background: r.color }} />
          <span className="font-semibold text-[var(--viz-ink)] tabular-nums">{r.value}</span>
          <span className="text-[var(--viz-ink-2)]">{r.label}</span>
        </p>
      ))}
    </div>
  )
}
