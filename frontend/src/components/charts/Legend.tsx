export function Legend({ items, kind }: { items: { label: string; color: string; icon?: string }[]; kind: 'rect' | 'line' }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--viz-ink-2)]" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          {kind === 'rect' ? <span className="inline-block size-2.5 rounded-sm" style={{ background: i.color }} /> : <span className="inline-block h-0.5 w-3.5 rounded" style={{ background: i.color }} />}
          {i.icon && <span aria-hidden="true">{i.icon}</span>}
          {i.label}
        </li>
      ))}
    </ul>
  )
}
