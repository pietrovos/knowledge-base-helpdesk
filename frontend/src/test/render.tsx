import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { routes } from '../router'

type Handler = (url: string, init?: RequestInit) => unknown

/** Route-level render with a fake fetch: handlers map "METHOD /path" to a JSON body (or a Response). */
export function renderApp(path: string, handlers: Record<string, Handler | unknown>) {
  const calls: { method: string; path: string; body?: unknown }[] = []
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const url = input.replace(/^\/api/, '')
    const key = `${method} ${url.split('?')[0]}`
    calls.push({ method, path: url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const handler = handlers[key]
    if (handler === undefined) return new Response(JSON.stringify({ detail: `unhandled ${key}` }), { status: 404, headers: { 'content-type': 'application/json' } })
    const result = typeof handler === 'function' ? (handler as Handler)(url, init) : handler
    if (result instanceof Response) return result
    return new Response(JSON.stringify(result), { headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return { ...utils, calls, router }
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
