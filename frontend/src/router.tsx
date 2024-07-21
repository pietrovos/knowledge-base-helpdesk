import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell, RequireAdmin } from './layout/AppShell'
import { GroupsPage } from './pages/admin/GroupsPage'
import { UsersPage } from './pages/admin/UsersPage'
import { CollectionDetailPage } from './pages/CollectionDetailPage'
import { CollectionsPage } from './pages/CollectionsPage'
import { LoginPage } from './pages/LoginPage'

export const routes = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/collections" replace /> },
      { path: 'collections', element: <CollectionsPage /> },
      { path: 'collections/:collectionId', element: <CollectionDetailPage /> },
      { path: 'admin/users', element: <RequireAdmin><UsersPage /></RequireAdmin> },
      { path: 'admin/groups', element: <RequireAdmin><GroupsPage /></RequireAdmin> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
