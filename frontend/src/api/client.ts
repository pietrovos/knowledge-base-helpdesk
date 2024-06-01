export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

type Json = Record<string, unknown> | unknown[]

export async function api<T>(path: string, init: RequestInit & { json?: Json } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const res = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...rest,
    headers: {
      ...(json ? { 'Content-Type': 'application/json' } : {}),
      'X-Requested-With': 'supportlens',
      ...headers,
    },
    body: json ? JSON.stringify(json) : rest.body,
  })
  if (res.status === 204) return undefined as T
  const body = res.headers.get('content-type')?.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) {
    const detail = typeof body === 'object' && body && 'detail' in body ? body.detail : body
    const message = typeof detail === 'string' ? detail : `Request failed (${res.status})`
    throw new ApiError(res.status, message, detail)
  }
  return body as T
}
