import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const now = new Date().toISOString()
const agent = { id: 2, name: 'Alex', email: 'a@x.dev', role: 'agent', is_active: true, groups: [] }
const admin = { ...agent, id: 1, name: 'Dana', role: 'admin' }
const ticket = {
  id: 5, subject: 'Refund timing', customer_name: 'Casey', customer_email: 'c@x.dev', status: 'open', priority: 'normal',
  assignee: null, escalation_reason: null, created_at: now, updated_at: now, preview: '', message_count: 1,
  messages: [{ id: 1, author_type: 'customer', author: null, body: 'When?', is_internal: false, draft_id: null, created_at: now }], events: [],
}
const draft = {
  id: 9, ticket_id: 5, status: 'ready', question: 'When?', custom_question: false,
  reply: 'Hi Casey,\n\nRefunds take 5 business days [41].', missing_information: '', invalid_citation_ids: [], error: null, error_kind: null,
  decided_by: 'model', provider: 'fake', model: 'fake', embedding_model: 'fake', retrieval_ms: 1, generation_ms: 1, best_similarity: 0.8,
  requested_by: agent, created_at: now, completed_at: now, published_text: null, was_edited: null, knowledge_gap_id: null,
  sources: [{ chunk_id: 41, document_id: 3, document_title: 'Refund Policy', version: 1, heading: 'Timing', text: 'Refunds take 5 business days.', rank: 1, similarity: 0.8, keyword_rank: 1, cited: true, accessible: true, live: true }],
}

test('edit & send publishes the edited text without citation markers', async () => {
  const { calls } = renderApp('/tickets/5', {
    'GET /auth/me': agent, 'GET /tickets/5': ticket, 'GET /users/directory': [agent], 'GET /tickets/5/drafts': [draft],
    'POST /drafts/9/publish': { ...draft, status: 'published' },
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Edit & send' }))
  const box = screen.getByLabelText('Reply to send')
  expect(box).toHaveValue('Hi Casey,\n\nRefunds take 5 business days.')
  await userEvent.type(box, '\n\nBest, Alex')
  expect(screen.getByText('Edited')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Send & resolve' }))
  await vi.waitFor(() =>
    expect(calls.find((c) => c.path === '/drafts/9/publish')?.body).toEqual({ text: 'Hi Casey,\n\nRefunds take 5 business days.\n\nBest, Alex', ticket_status: 'resolved' }),
  )
})

test('escalations page lists reasons and can de-escalate', async () => {
  const { calls } = renderApp('/escalations', {
    'GET /auth/me': agent,
    'GET /tickets': { items: [{ ...ticket, status: 'escalated', escalation_reason: 'Legal threat' }], total: 1, page: 1, page_size: 100 },
    'PATCH /tickets/5': ticket,
  })
  expect(await screen.findByText('Legal threat')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'De-escalate' }))
  await vi.waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'open' }))
})

test('admins resolve knowledge gaps with a note; agents only view', async () => {
  const gap = { id: 3, ticket_id: 5, draft_id: 9, question: 'Do you ship to Antarctica?', missing_information: 'No shipping coverage doc', status: 'open', created_by: agent, resolved_by: null, resolution_note: null, resolved_document_id: null, created_at: now, resolved_at: null }
  const { calls } = renderApp('/knowledge-gaps', { 'GET /auth/me': admin, 'GET /knowledge-gaps': [gap], 'PATCH /knowledge-gaps/3': { ...gap, status: 'resolved' } })
  const card = await screen.findByText('“Do you ship to Antarctica?”')
  const list = screen.getByRole('list', { name: 'Knowledge gaps' })
  expect(card).toBeInTheDocument()
  await userEvent.click(within(list).getByRole('button', { name: 'Resolve' }))
  await userEvent.type(screen.getByLabelText('Resolution note'), 'Added shipping FAQ')
  await userEvent.click(screen.getByRole('button', { name: 'Mark resolved' }))
  await vi.waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'resolved', resolution_note: 'Added shipping FAQ' }))
})

test('agents see the gap queue read-only', async () => {
  const gap = { id: 3, ticket_id: null, draft_id: null, question: 'Q?', missing_information: '', status: 'open', created_by: agent, resolved_by: null, resolution_note: null, resolved_document_id: null, created_at: now, resolved_at: null }
  renderApp('/knowledge-gaps', { 'GET /auth/me': agent, 'GET /knowledge-gaps': [gap] })
  expect(await screen.findByText('“Q?”')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument()
})
