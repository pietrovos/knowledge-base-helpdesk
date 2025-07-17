import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const now = new Date().toISOString()
const agent = { id: 2, name: 'Alex', email: 'a@x.dev', role: 'agent', is_active: true, groups: [] }
const ticket = {
  id: 5, subject: 'Refund', customer_name: 'Casey', customer_email: 'c@x.dev', status: 'open', priority: 'normal', assignee: null,
  escalation_reason: null, created_at: now, updated_at: now, preview: '', message_count: 1,
  messages: [{ id: 1, author_type: 'customer', author: null, body: 'Hi', is_internal: false, draft_id: null, created_at: now }], events: [],
}
const degraded = {
  drafting_available: false, worker_online: true, embedding_provider: 'local',
  llm: { provider: 'anthropic', model: 'claude-opus-5-5', state: 'open', retry_in_seconds: 22, recent_failures: 3, last_error: 'unavailable: 503', simulated_outage: 'none' },
  degraded_reasons: ['The model provider is failing; AI drafts are paused.'],
}

test('degraded mode: banner shown, drafting disabled, manual reply still available', async () => {
  renderApp('/tickets/5', {
    'GET /auth/me': agent, 'GET /tickets/5': ticket, 'GET /users/directory': [agent], 'GET /tickets/5/drafts': [],
    'GET /system/status': degraded, 'GET /tickets/counts': {}, 'GET /knowledge-gaps/counts': {},
  })
  expect(await screen.findByTestId('degraded-banner')).toHaveTextContent('trial request in ~22s')
  expect(await screen.findByTestId('drafting-paused')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Draft reply' })).toBeDisabled()
  expect(screen.getByLabelText('Message')).toBeEnabled()
})

test('healthy system shows no banner', async () => {
  renderApp('/tickets/5', {
    'GET /auth/me': agent, 'GET /tickets/5': ticket, 'GET /users/directory': [agent], 'GET /tickets/5/drafts': [],
    'GET /system/status': { ...degraded, drafting_available: true, degraded_reasons: [], llm: { ...degraded.llm, state: 'closed', retry_in_seconds: null } },
  })
  expect(await screen.findByRole('button', { name: 'Draft reply' })).toBeEnabled()
  expect(screen.queryByTestId('degraded-banner')).not.toBeInTheDocument()
})
