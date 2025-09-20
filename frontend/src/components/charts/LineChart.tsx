import { useState } from 'react'
import { niceTicks, shortDate } from './scale'
import { Tooltip } from './Tooltip'

export interface LineSeries {
  key: string
  label: string
  color: string
}

const H = 180
const PAD = { top: 8, right: 44, bottom: 22, left: 44 }

/** Lines over days with a snapping crosshair. Missing values break the line. */
export function LineChart({ data, series, format, label }: { data: Record<string, unknown>[]; series: LineSeries[]; format: (v: number) => string; label: string }) {
  const [width, setWidth] = useState(640)
  const [hover, setHover] = useState<number | null>(null)
  const values = data.flatMap((d) => series.map((s) => d[s.key] as number | null)).filter((v): v is number => v != null)
  const ticks = niceTicks(Math.max(...values, 0))
  const yMax = ticks[ticks.length - 1]
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW)
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH
  const labelEvery = Math.ceil(data.length / 7)

  const path = (key: string) => {
    let d = ''
    let pen = false
    data.forEach((row, i) => {
      const v = row[key] as number | null
      if (v == null) {
        pen = false
        return
      }
      d += `${pen ? 'L' : 'M'}${x(i)},${y(v)} `
      pen = true
    })
    return d
  }
  const lastIndex = (key: string) => data.map((r) => r[key]).findLastIndex((v) => v != null)
  // Direct end labels only when they can't collide; otherwise the legend carries identity.
  const ends = series.map((s) => {
    const i = lastIndex(s.key)
    return i >= 0 ? y(data[i][s.key] as number) : null
  })
  const endLabels = ends.every((a, i) => a == null || ends.every((b, j) => j === i || b == null || Math.abs(a - b) >= 12))

  return (
    <div
      ref={(el) => {
        if (el && Math.abs(el.clientWidth - width) > 4) setWidth(el.clientWidth)
      }}
      className="relative"
      onPointerLeave={() => setHover(null)}
      onPointerMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect()
        const i = Math.round(((e.clientX - rect.left - PAD.left) / innerW) * (data.length - 1))
        setHover(Math.max(0, Math.min(data.length - 1, i)))
      }}
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
        {data.map((d, i) =>
          i % labelEvery === 0 ? (
            <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="fill-[var(--viz-muted)] text-[10px]">
              {shortDate(String(d.day))}
            </text>
          ) : null,
        )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--viz-axis)" strokeWidth={1} />}
        {series.map((s) => {
          const li = lastIndex(s.key)
          return (
            <g key={s.key}>
              <path d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {data.map((row, i) => {
                const v = row[s.key] as number | null
                return v != null && (i === hover || i === li) ? <circle key={i} cx={x(i)} cy={y(v)} r={4} fill={s.color} stroke="var(--viz-surface)" strokeWidth={2} /> : null
              })}
              {li >= 0 && endLabels && (
                <text x={x(li) + 8} y={y(data[li][s.key] as number)} dy="0.32em" className="fill-[var(--viz-ink-2)] text-[10px]">
                  {s.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <Tooltip
          x={x(hover)}
          y={PAD.top}
          width={width}
          title={shortDate(String(data[hover].day))}
          rows={series.map((s) => ({ color: s.color, label: s.label, value: data[hover][s.key] == null ? '—' : format(data[hover][s.key] as number) }))}
        />
      )}
    </div>
  )
}
