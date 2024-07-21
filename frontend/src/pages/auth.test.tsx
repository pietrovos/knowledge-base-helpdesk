import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { json, renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const agent = { id: 2, name: 'Alex Rivera', email: 'alex@x.dev', role: 'agent', is_active: true, groups: [] }
const admin = { ...agent, id: 1, name: 'Dana', role: 'admin' }
const collections = [{ id: 7, name: 'Customer Policies', description: 'Refunds', created_at: '', document_count: 3 }]

test('unauthenticated users are sent to login, and signing in lands on Knowledge', async () => {
  let loggedIn = false
  const { calls } = renderApp('/collections', {
    'GET /auth/me': () => (loggedIn ? agent : json({ detail: 'Not authenticated' }, 401)),
    'POST /auth/login': () => {
      loggedIn = true
      return agent
    },
    'GET /collections': collections,
  })
  await userEvent.type(await screen.findByLabelText('Email'), 'alex@x.dev')
  await userEvent.type(screen.getByLabelText('Password'), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByText('Customer Policies')).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/auth/login')?.body).toEqual({ email: 'alex@x.dev', password: 'pw' })
})

test('agents do not see admin navigation', async () => {
  renderApp('/collections', { 'GET /auth/me': agent, 'GET /collections': collections })
  const nav = await screen.findByRole('navigation', { name: 'Main', hidden: true })
  expect(within(nav).queryByText('Users')).not.toBeInTheDocument()
  expect(within(nav).getByText('Knowledge')).toBeInTheDocument()
})

test('agents are redirected away from admin pages', async () => {
  renderApp('/admin/users', { 'GET /auth/me': agent, 'GET /collections': collections })
  expect(await screen.findByText('Customer Policies')).toBeInTheDocument()
})

test('admin can revoke a grant from the access panel', async () => {
  const grants = [{ id: 11, collection_id: 7, group: { id: 3, name: 'Tier 1 Support' }, user: null, created_at: '' }]
  const { calls } = renderApp('/collections/7', {
    'GET /auth/me': admin,
    'GET /collections/7': collections[0],
    'GET /collections/7/grants': grants,
    'GET /groups': [],
    'GET /users': [],
    'DELETE /collections/7/grants/11': () => new Response(null, { status: 204 }),
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Revoke Tier 1 Support' }))
  expect(calls.some((c) => c.method === 'DELETE' && c.path === '/collections/7/grants/11')).toBe(true)
})
