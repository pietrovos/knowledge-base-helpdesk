import { Link, isRouteErrorResponse, useRouteError } from 'react-router'

export function RouteError() {
  const error = useRouteError()
  const notFound = isRouteErrorResponse(error) && error.status === 404
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-16">
      <div className="max-w-md text-center">
        <p className="text-sm font-semibold text-indigo-600">{notFound ? '404' : 'Something went wrong'}</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">{notFound ? 'Page not found' : 'This page hit an unexpected error'}</h1>
        <p className="mt-2 text-sm text-slate-600">
          {notFound ? 'The link may be outdated.' : 'Your data is safe. Reload the page, or head back to the inbox.'}
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button onClick={() => window.location.reload()} className="rounded-md bg-white px-3.5 py-2 text-sm font-medium ring-1 ring-slate-300 hover:bg-slate-50">
            Reload
          </button>
          <Link to="/tickets" className="rounded-md bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500">
            Go to inbox
          </Link>
        </div>
      </div>
    </div>
  )
}
