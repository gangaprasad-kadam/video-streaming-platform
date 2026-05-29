import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()
  return (
    <nav style={{ padding: '1rem', background: '#1a1a1a', display: 'flex', gap: '1rem', alignItems: 'center' }}>
      <Link to="/" style={{ fontWeight: 'bold', fontSize: '1.2rem' }}>📹 StreamApp</Link>
      <Link to="/browse">Browse</Link>
      {user ? (
        <>
          <Link to="/upload">Upload</Link>
          <Link to="/dashboard">Dashboard</Link>
          <span style={{ marginLeft: 'auto' }}>{user.name || user.email}</span>
          <button onClick={logout}>Logout</button>
        </>
      ) : (
        <span style={{ marginLeft: 'auto' }}>
          <Link to="/login">Login</Link>
          {' | '}
          <Link to="/register">Register</Link>
        </span>
      )}
    </nav>
  )
}
