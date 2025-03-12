import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { json, renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const me = { id: 2, name: 'Alex', email: 'a@x.dev', role: 'agent', is_active: true, groups: [] }
const now = new Date().toISOString()
const ticket = {
  id: 5, subject: 'Refund timing', customer_name: 'Casey', customer_email: 'c@x.dev', status: 'open', priority: 'normal',
  assignee: null, created_at: now, updated_at: now, preview: '', message_count: 1, escalation_reason: null,
  messages: [{ id: 1, author_type: 'customer', author: null, body: 'When do I get my refund?', is_internal: false, draft_id: null, created_at: now }],
  events: [],
}
const source = (over: object) => ({
  chunk_id: 41, document_id: 3, document_title: 'Refund Policy', version: 2, heading: 'Timing', text: 'Refunds are issued within 5 business days.',
  rank: 1, similarity: 0.81, keyword_rank: 1, cited: true, accessible: true, live: true, ...over,
})
const draft = (over: object) => ({
  id: 9, ticket_id: 5, status: 'ready', question: 'When do I get my refund?', custom_question: false,
  reply: 'Hi Casey,\n\nRefunds are issued within 5 business days [41].', missing_information: '', invalid_citation_ids: [],
  error: null, error_kind: null, decided_by: 'model', provider: 'fake', model: 'fake-extractive-1', embedding_model: 'fake',
  retrieval_ms: 12, generation_ms: 40, best_similarity: 0.81, requested_by: me, created_at: now, completed_at: now,
  published_text: null, was_edited: null, knowledge_gap_id: null,
  sources: [source({}), source({ chunk_id: 42, rank: 2, cited: false, heading: 'Gift cards', text: 'Gift cards are final sale.' })],
  ...over,
})
const base = { 'GET /auth/me': me, 'GET /tickets/5': ticket, 'GET /users/directory': [me] }

test('citations render as numbered chips that open the exact passage', async () => {
  renderApp('/tickets/5', {
    ...base,
    'GET /tickets/5/drafts': [draft({})],
    'GET /drafts/9/evidence/41': { source: source({}), context_before: 'Earlier paragraph.', context_after: null, collection_name: 'Customer Policies' },
  })
  const reply = await screen.findByTestId('draft-reply')
  expect(reply).toHaveTextContent('Refunds are issued within 5 business days')
  await userEvent.click(within(reply).getByRole('button', { name: 'Citation 1' }))
  const dialog = await screen.findByRole('dialog', { name: 'Evidence for citation 1' })
  expect(await within(dialog).findByTestId('evidence-passage')).toHaveTextContent('Refunds are issued within 5 business days.')
  expect(within(dialog).getByText('Customer Policies')).toBeInTheDocument()
})

test('revoked access shows a clear message in the evidence drawer', async () => {
  renderApp('/tickets/5', {
    ...base,
    'GET /tickets/5/drafts': [draft({})],
    'GET /drafts/9/evidence/41': () => json({ detail: 'You no longer have access to this source' }, 403),
  })
  await userEvent.click(within(await screen.findByTestId('draft-reply')).getByRole('button', { name: 'Citation 1' }))
  expect(await screen.findByText(/You no longer have access to this source/)).toBeInTheDocument()
})

test('removed citations are flagged', async () => {
  renderApp('/tickets/5', { ...base, 'GET /tickets/5/drafts': [draft({ invalid_citation_ids: [999] })] })
  expect(await screen.findByRole('note')).toHaveTextContent('1 citation was removed')
})

test('insufficient evidence offers a knowledge-gap task', async () => {
  const { calls } = renderApp('/tickets/5', {
    ...base,
    'GET /tickets/5/drafts': [draft({ status: 'insufficient_evidence', reply: '', decided_by: 'evidence_gate', missing_information: 'Nothing covers router firmware', sources: [] })],
    'POST /knowledge-gaps': { id: 3 },
  })
  const box = await screen.findByTestId('insufficient-evidence')
  expect(box).toHaveTextContent('Nothing covers router firmware')
  await userEvent.click(within(box).getByRole('button', { name: 'Create knowledge-gap task' }))
  await vi.waitFor(() => expect(calls.find((c) => c.method === 'POST' && c.path === '/knowledge-gaps')?.body).toEqual({ draft_id: 9 }))
})

test('provider failure keeps the ticket usable', async () => {
  renderApp('/tickets/5', {
    ...base,
    'GET /tickets/5/drafts': [draft({ status: 'failed', reply: '', error: 'Model provider error (503)', error_kind: 'unavailable', sources: [] })],
  })
  expect(await screen.findByTestId('draft-failed')).toHaveTextContent('The ticket is fully usable')
  expect(screen.getByRole('button', { name: 'Send reply' })).toBeInTheDocument()
})
