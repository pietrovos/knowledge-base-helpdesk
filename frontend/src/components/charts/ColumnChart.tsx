import { useRef, useState } from 'react'
import { niceTicks, shortDate } from './scale'
import { Tooltip } from './Tooltip'

export interface ColumnSeries {
  key: string
  label: string
  color: string
}

const H = 180
const PAD = { top: 8, right: 8, bottom: 22, left: 40 }

/** Stacked columns over days. Each column is its own hover/focus target. */
export function ColumnChart({ data, series, format, label }: { data: Record<string, unknown>[]; series: ColumnSeries[]; format: (v: number) => string; label: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [hover, setHover] = useState<number | null>(null)
  const rows = data
  const totals = rows.map((d) => series.reduce((s, x) => s + Number(d[x.key] ?? 0), 0))
  const ticks = niceTicks(Math.max(...totals, 0))
  const yMax = ticks[ticks.length - 1]
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const band = innerW / Math.max(rows.length, 1)
  const barW = Math.min(24, Math.max(3, band - 4))
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH
  const labelEvery = Math.ceil(rows.length / 7)

  return (
    <div
      ref={(el) => {
        ref.current = el
        if (el && Math.abs(el.clientWidth - width) > 4) setWidth(el.clientWidth)
      }}
      className="relative"
      onPointerLeave={() => setHover(null)}
    >
      <svg width={width} height={H} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? 'var(--viz-axis)' : 'var(--viz-grid)'} strokeWidth={1} />
            <text x={PAD.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="fill-[var(--viz-muted)] text-[10px] tabular-nums">
              {format(t)}
            </text>
          </g>
        ))}
        {rows.map((d, i) => {
          const cx = PAD.left + band * i + band / 2
          let acc = 0
          const segs = series.map((s) => {
            const v = Number(d[s.key] ?? 0)
            const seg = { s, y0: acc, y1: acc + v }
            acc += v
            return seg
          }).filter((g) => g.y1 > g.y0)
          return (
            <g key={i}>
              {segs.map((g, j) => {
                const top = y(g.y1)
                const bottom = y(g.y0) - (j > 0 ? 2 : 0) // 2px surface gap between stacked segments
                const h = Math.max(1, bottom - top)
                const r = j === segs.length - 1 ? Math.min(4, h / 2, barW / 2) : 0 // rounded data-end only
                return (
                  <path
                    key={g.s.key}
                    d={`M${cx - barW / 2},${top + h} V${top + r} Q${cx - barW / 2},${top} ${cx - barW / 2 + r},${top} H${cx + barW / 2 - r} Q${cx + barW / 2},${top} ${cx + barW / 2},${top + r} V${top + h} Z`}
                    fill={g.s.color}
                    opacity={hover === null || hover === i ? 1 : 0.55}
                  />
                )
              })}
              {i % labelEvery === 0 && (
                <text x={cx} y={H - 6} textAnchor="middle" className="fill-[var(--viz-muted)] text-[10px]">
                  {shortDate(String(d.day))}
                </text>
              )}
              <rect
                x={PAD.left + band * i}
                y={PAD.top}
                width={band}
                height={innerH}
                fill="transparent"
                tabIndex={0}
                aria-label={`${shortDate(String(d.day))}: ${series.map((s) => `${s.label} ${format(Number(d[s.key] ?? 0))}`).join(', ')}`}
                onPointerEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
              />
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <Tooltip
          x={PAD.left + band * hover + band / 2}
          y={y(totals[hover])}
          width={width}
          title={shortDate(String(rows[hover].day))}
          rows={series.map((s) => ({ color: s.color, label: s.label, value: format(Number(rows[hover][s.key] ?? 0)) }))}
        />
      )}
    </div>
  )
}
