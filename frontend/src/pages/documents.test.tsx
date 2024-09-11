import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { renderApp } from '../test/render'

afterEach(() => vi.unstubAllGlobals())

const agent = { id: 2, name: 'Alex', email: 'a@x.dev', role: 'agent', is_active: true, groups: [] }
const version = (over: object) => ({
  id: 1, version: 1, status: 'ready', progress: 100, stage: 'done', error: null, attempts: 1, chunk_count: 4,
  size_bytes: 2048, sha256: 'x', embedding_model: 'fake', created_at: new Date().toISOString(), processed_at: null, ...over,
})

test('collection documents show live, processing and failed states', async () => {
  const live = version({})
  renderApp('/collections/7', {
    'GET /auth/me': agent,
    'GET /collections/7': { id: 7, name: 'Policies', description: '', created_at: '', document_count: 3 },
    'GET /collections/7/documents': [
      { id: 1, collection_id: 7, title: 'Refunds', filename: 'refunds.md', created_at: '', current_version: live, latest_version: live },
      { id: 2, collection_id: 7, title: 'Shipping', filename: 'shipping.md', created_at: '', current_version: null, latest_version: version({ id: 2, status: 'processing', stage: 'embedding', progress: 60 }) },
      { id: 3, collection_id: 7, title: 'Warranty', filename: 'warranty.md', created_at: '', current_version: live, latest_version: version({ id: 3, version: 2, status: 'failed', stage: 'failed', error: 'Embedding provider error' }) },
    ],
  })
  expect(await screen.findByText('Refunds')).toBeInTheDocument()
  expect(screen.getByText('Live')).toBeInTheDocument()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60')
  expect(screen.getByText('v2 failed: Embedding provider error')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Upload document' })).not.toBeInTheDocument()
})
