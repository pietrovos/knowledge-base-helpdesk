import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const me = { id: 2, name: 'Alex', email: 'a@x.dev', role: 'agent', is_active: true, groups: [] }
const now = new Date().toISOString()
const summary = {
  id: 5, subject: 'Refund not received', customer_name: 'Casey', customer_email: 'casey@example.com', status: 'open',
  priority: 'urgent', assignee: null, created_at: now, updated_at: now, preview: 'I returned it', message_count: 1,
}
const detail = {
  ...summary, escalation_reason: null,
  messages: [{ id: 1, author_type: 'customer', author: null, body: 'I returned it two weeks ago.', is_internal: false, draft_id: null, created_at: now }],
  events: [{ id: 1, kind: 'created', actor: me, data: {}, created_at: now }],
}

test('inbox lists tickets with counts and switches views', async () => {
  const { calls } = renderApp('/tickets', {
    'GET /auth/me': me,
    'GET /tickets/counts': { active: 4, mine: 1, unassigned: 2, pending: 0, escalated: 1 },
    'GET /tickets': { items: [summary], total: 1, page: 1, page_size: 25 },
  })
  expect(await screen.findByText('Refund not received')).toBeInTheDocument()
  expect(screen.getByText('Urgent')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Escalated/ }))
  await vi.waitFor(() => expect(calls.some((c) => c.path.includes('view=escalated'))).toBe(true))
})

test('escalating requires a reason and sends it', async () => {
  const { calls } = renderApp('/tickets/5', {
    'GET /auth/me': me,
    'GET /tickets/5': detail,
    'GET /users/directory': [me],
    'PATCH /tickets/5': { ...detail, status: 'escalated', escalation_reason: 'Chargeback threat' },
  })
  await userEvent.selectOptions(await screen.findByLabelText('Status'), 'escalated')
  const escalate = screen.getByRole('button', { name: 'Escalate' })
  expect(escalate).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Why does this need escalation?'), 'Chargeback threat')
  await userEvent.click(escalate)
  await vi.waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'escalated', escalation_reason: 'Chargeback threat' }))
})

test('sending a reply posts the message', async () => {
  const { calls } = renderApp('/tickets/5', {
    'GET /auth/me': me,
    'GET /tickets/5': detail,
    'GET /users/directory': [me],
    'POST /tickets/5/messages': { id: 2 },
  })
  await userEvent.type(await screen.findByLabelText('Message'), 'Your refund was issued today.')
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }))
  await vi.waitFor(() => expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ body: 'Your refund was issued today.', is_internal: false }))
})
