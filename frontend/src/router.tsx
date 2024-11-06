import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell, RequireAdmin } from './layout/AppShell'
import { GroupsPage } from './pages/admin/GroupsPage'
import { UsersPage } from './pages/admin/UsersPage'
import { CollectionDetailPage } from './pages/CollectionDetailPage'
import { CollectionsPage } from './pages/CollectionsPage'
import { DocumentPage } from './pages/DocumentPage'
import { InboxPage } from './pages/InboxPage'
import { LoginPage } from './pages/LoginPage'
import { TicketPage } from './pages/TicketPage'

export const routes = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/tickets" replace /> },
      { path: 'tickets', element: <InboxPage /> },
      { path: 'tickets/:ticketId', element: <TicketPage /> },
      { path: 'collections', element: <CollectionsPage /> },
      { path: 'collections/:collectionId', element: <CollectionDetailPage /> },
      { path: 'documents/:documentId', element: <DocumentPage /> },
      { path: 'admin/users', element: <RequireAdmin><UsersPage /></RequireAdmin> },
      { path: 'admin/groups', element: <RequireAdmin><GroupsPage /></RequireAdmin> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
