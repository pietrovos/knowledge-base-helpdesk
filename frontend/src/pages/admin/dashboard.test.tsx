import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { renderApp } from '../../test/render'

afterEach(() => vi.unstubAllGlobals())

const admin = { id: 1, name: 'Dana', email: 'd@x.dev', role: 'admin', is_active: true, groups: [] }
const day = (d: string, over: object = {}) => ({ day: d, calls: 4, errors: 1, cost_usd: 0.05, input_tokens: 8000, output_tokens: 900, latency_p50_ms: 4200, latency_p95_ms: 9100, ...over })
const overview = {
  days: 7,
  totals: { calls: 8, errors: 2, error_rate: 0.25, input_tokens: 16000, output_tokens: 1800, cost_usd: 0.1, latency_p50_ms: 4200, latency_p95_ms: 9100 },
  daily: [day('2026-10-04'), day('2026-10-05')],
  by_model: [{ model: 'claude-opus-5-5', calls: 8, cost_usd: 0.1 }],
  by_status: { ok: 6, timeout: 2 },
  drafts: { total: 9, by_status: { ready: 4, insufficient_evidence: 3, failed: 2 }, evidence_gate_refusals: 2, published: 3, published_unedited: 2, drafts_with_removed_citations: 1, avg_citations_per_answer: 2.3, retrieval_p50_ms: 12, retrieval_p95_ms: 30 },
  recent_failures: [{ created_at: new Date().toISOString(), status: 'timeout', model: 'claude-opus-5-5', error: 'No response within 50s', latency_ms: 50000 }],
}

test('dashboard shows tiles, charts with legends, outcomes and a table view', async () => {
  const { calls } = renderApp('/admin/usage', { 'GET /auth/me': admin, 'GET /metrics/overview': overview, 'GET /system/status': {} })
  expect(await screen.findByText('$0.10')).toBeInTheDocument()
  expect(screen.getByText('9.1 s')).toBeInTheDocument()
  expect(screen.getByText('25%')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Model calls per day, succeeded and failed' })).toBeInTheDocument()
  expect(screen.getAllByRole('list', { name: 'Legend' })).toHaveLength(2)
  expect(screen.getByText(/No response within 50s/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Show table' }))
  expect(screen.getAllByRole('row')).toHaveLength(3)
  await userEvent.click(screen.getByRole('button', { name: /30 days/ }))
  await vi.waitFor(() => expect(calls.some((c) => c.path === '/metrics/overview?days=30')).toBe(true))
})
