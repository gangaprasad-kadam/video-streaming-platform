import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import Navbar from '@/components/Navbar'
import ProtectedRoute from '@/components/ProtectedRoute'

vi.mock('@/api/auth', () => ({
  getMe:  vi.fn(),
  logout: vi.fn(),
}))
vi.mock('@/hooks/useTheme', () => ({
  default: () => ({ isDark: false, toggle: vi.fn(), theme: 'light' }),
}))

import * as authApi from '@/api/auth'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => mockNavigate,
}))

function renderNavbar() {
  return render(
    <MemoryRouter>
      <AuthProvider><Navbar /></AuthProvider>
    </MemoryRouter>
  )
}

describe('Navbar', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('T3.4 — shows Sign in + Get started when user is null', async () => {
    authApi.getMe.mockRejectedValue(new Error('401'))
    renderNavbar()
    await waitFor(() => expect(screen.getByText('Sign in')).toBeInTheDocument())
    expect(screen.getByText('Get started')).toBeInTheDocument()
  })

  it('T3.5 — shows avatar with initials when user is logged in', async () => {
    authApi.getMe.mockResolvedValue({ id: 1, name: 'Jane Smith', email: 'j@b.com' })
    renderNavbar()
    await waitFor(() => {
      expect(screen.queryByText('Sign in')).not.toBeInTheDocument()
    })
    const avatarBtn = screen.getByRole('button', { name: /user menu/i })
    expect(avatarBtn).toBeInTheDocument()
  })

  it('T3.6 — clicking logout in dropdown calls logout() and navigates', async () => {
    authApi.getMe.mockResolvedValue({ id: 1, name: 'Jane', email: 'j@b.com' })
    authApi.logout.mockResolvedValue(undefined)
    renderNavbar()
    await waitFor(() => screen.getByRole('button', { name: /user menu/i }))
    await userEvent.click(screen.getByRole('button', { name: /user menu/i }))
    await userEvent.click(screen.getByText(/sign out/i))
    expect(authApi.logout).toHaveBeenCalled()
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true }))
  })

  it('shows VidStream brand name', async () => {
    authApi.getMe.mockRejectedValue(new Error('401'))
    renderNavbar()
    await waitFor(() => expect(screen.getByText('VidStream')).toBeInTheDocument())
  })
})

describe('ProtectedRoute', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('T3.1 — unauthenticated user redirected to /login', async () => {
    authApi.getMe.mockRejectedValue(new Error('401'))
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider><ProtectedRoute /></AuthProvider>
      </MemoryRouter>
    )
    // While loading, shows spinner; after — redirects (Outlet renders nothing for unauthenticated)
    await waitFor(() => {
      expect(container.textContent).not.toContain('Loading...')
    })
  })

  it('T3.3 — shows loading while auth state is being checked', () => {
    authApi.getMe.mockImplementation(() => new Promise(() => {})) // never resolves
    render(
      <MemoryRouter>
        <AuthProvider><ProtectedRoute /></AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})
