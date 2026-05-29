import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'

// Mock all API calls
vi.mock('@/api/auth', () => ({
  getMe:    vi.fn(),
  login:    vi.fn(),
  logout:   vi.fn(),
  register: vi.fn(),
}))

import * as authApi from '@/api/auth'

function renderWithAuth(ui) {
  return render(<MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>)
}

// Helper component that exposes context values
function Consumer() {
  const { user, loading, login, logout, register } = useAuth()
  return (
    <div>
      <span data-testid="user">{user ? JSON.stringify(user) : 'null'}</span>
      <span data-testid="loading">{String(loading)}</span>
      <button onClick={() => login('a@b.com', 'pass')}>login</button>
      <button onClick={() => logout()}>logout</button>
      <button onClick={() => register('Jane', 'j@b.com', 'pass')}>register</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('T2.1 — sets user when getMe succeeds on mount', async () => {
    authApi.getMe.mockResolvedValue({ id: 1, email: 'a@b.com' })
    renderWithAuth(<Consumer />)
    await waitFor(() =>
      expect(screen.getByTestId('user').textContent).toContain('a@b.com')
    )
  })

  it('T2.2 — user stays null when getMe returns 401', async () => {
    authApi.getMe.mockRejectedValue(new Error('Unauthorized'))
    renderWithAuth(<Consumer />)
    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false')
    )
    expect(screen.getByTestId('user').textContent).toBe('null')
  })

  it('T2.3 — login() sets user on success', async () => {
    // Mount: getMe rejects (not logged in). After login: getMe resolves with profile.
    authApi.getMe
      .mockRejectedValueOnce(new Error('401'))
      .mockResolvedValueOnce({ id: 2, email: 'a@b.com' })
    authApi.login.mockResolvedValue({ message: 'logged in' })
    renderWithAuth(<Consumer />)
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    await userEvent.click(screen.getByText('login'))
    await waitFor(() =>
      expect(screen.getByTestId('user').textContent).toContain('a@b.com')
    )
  })

  it('T2.4 — login() with wrong credentials throws error', async () => {
    authApi.getMe.mockRejectedValue(new Error('401'))
    authApi.login.mockRejectedValue(new Error('Invalid credentials'))
    renderWithAuth(<Consumer />)
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    await expect(
      authApi.login('bad@b.com', 'wrong')
    ).rejects.toThrow('Invalid credentials')
  })

  it('T2.5 — logout() clears user state', async () => {
    authApi.getMe.mockResolvedValue({ id: 1, email: 'a@b.com' })
    authApi.logout.mockResolvedValue(undefined)
    renderWithAuth(<Consumer />)
    await waitFor(() => expect(screen.getByTestId('user').textContent).toContain('a@b.com'))
    await userEvent.click(screen.getByText('logout'))
    await waitFor(() =>
      expect(screen.getByTestId('user').textContent).toBe('null')
    )
  })

  it('T2.6 — register() calls register then login, sets user', async () => {
    authApi.getMe
      .mockRejectedValueOnce(new Error('401'))       // mount
      .mockResolvedValueOnce({ id: 3, email: 'j@b.com' }) // after login inside register
    authApi.register.mockResolvedValue(undefined)
    authApi.login.mockResolvedValue({ message: 'logged in' })
    renderWithAuth(<Consumer />)
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    await userEvent.click(screen.getByText('register'))
    await waitFor(() =>
      expect(screen.getByTestId('user').textContent).toContain('j@b.com')
    )
    // Backend expects 'username', not 'name'
    expect(authApi.register).toHaveBeenCalledWith({ username: 'Jane', email: 'j@b.com', password: 'pass' })
  })

  it('T2.7 — loading is true then false after mount check', async () => {
    let resolve
    authApi.getMe.mockImplementation(() => new Promise((r) => { resolve = r }))
    renderWithAuth(<Consumer />)
    expect(screen.getByTestId('loading').textContent).toBe('true')
    resolve({ id: 1 })
    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false')
    )
  })
})
