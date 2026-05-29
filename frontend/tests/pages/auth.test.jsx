import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/api/auth', () => ({
  getMe:    vi.fn().mockRejectedValue(new Error('401')),
  login:    vi.fn(),
  logout:   vi.fn(),
  register: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => mockNavigate,
}))

import * as authApi from '@/api/auth'
import { AuthProvider } from '@/context/AuthContext'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider><LoginPage /></AuthProvider>
    </MemoryRouter>
  )
}
function renderRegister() {
  return render(
    <MemoryRouter>
      <AuthProvider><RegisterPage /></AuthProvider>
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => { vi.clearAllMocks(); authApi.getMe.mockRejectedValue(new Error('401')) })

  it('T2.8 — renders email + password fields + submit', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('T2.9 — valid credentials: calls login and navigates to /', async () => {
    // Mount: getMe rejects. After login: getMe resolves with user profile.
    authApi.getMe
      .mockRejectedValueOnce(new Error('401'))
      .mockResolvedValueOnce({ id: 1, email: 'a@b.com' })
    authApi.login.mockResolvedValue({ message: 'logged in' })
    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }))
  })

  it('T2.10 — server error shows error message', async () => {
    authApi.login.mockRejectedValue(new Error('Invalid credentials'))
    renderLogin()
    await userEvent.type(screen.getByLabelText(/email/i), 'bad@b.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrongpass')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(screen.getByText('Invalid credentials')).toBeInTheDocument())
  })

  it('shows validation error for empty email', async () => {
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(screen.getByText(/email is required/i)).toBeInTheDocument()
  })
})

describe('RegisterPage', () => {
  beforeEach(() => { vi.clearAllMocks(); authApi.getMe.mockRejectedValue(new Error('401')) })

  it('T2.11 — renders name + email + password + confirm fields', () => {
    renderRegister()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
  })

  it('T2.12 — password mismatch shows inline error', async () => {
    renderRegister()
    await userEvent.type(screen.getByLabelText(/full name/i), 'Jane')
    await userEvent.type(screen.getByLabelText(/email/i), 'j@b.com')
    await userEvent.type(screen.getByLabelText(/^password/i), 'pass123')
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'different')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))
    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
  })
})
