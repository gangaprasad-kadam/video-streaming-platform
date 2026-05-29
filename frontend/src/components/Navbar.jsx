import { useState, useRef, useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import useTheme from '@/hooks/useTheme'
import s from './Navbar.module.css'

function initials(user) {
  const name = user?.name || user?.email || '?'
  return name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const { isDark, toggle } = useTheme()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = async () => {
    setOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const navLinkClass = ({ isActive }) =>
    `${s.navLink} ${isActive ? s.navLinkActive : ''}`

  return (
    <header className={s.navbar} role="banner">
      <div className={s.inner}>
        {/* Logo */}
        <Link to="/" className={s.logo} aria-label="VidStream home">
          <div className={s.logoIcon} aria-hidden>▶</div>
          <span className={s.logoText}>VidStream</span>
        </Link>

        {/* Primary nav */}
        <nav className={s.nav} aria-label="Main navigation">
          <NavLink to="/"       className={navLinkClass} end>Home</NavLink>
          <NavLink to="/browse" className={navLinkClass}>Browse</NavLink>
          {user && (
            <NavLink to="/dashboard" className={navLinkClass}>Dashboard</NavLink>
          )}
        </nav>

        <div className={s.spacer} />

        <div className={s.actions}>
          {/* Theme toggle */}
          <button
            className={s.themeBtn}
            onClick={toggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Light mode' : 'Dark mode'}
          >
            {isDark ? '☀️' : '🌙'}
          </button>

          {user ? (
            <>
              <Link to="/upload" className={s.uploadBtn}>
                <span aria-hidden>＋</span> Upload
              </Link>

              {/* User avatar + dropdown */}
              <div className={s.userMenu} ref={menuRef}>
                <button
                  className={s.avatar}
                  onClick={() => setOpen((o) => !o)}
                  aria-label="User menu"
                  aria-expanded={open}
                  aria-haspopup="true"
                >
                  {initials(user)}
                </button>

                {open && (
                  <div className={s.dropdown} role="menu">
                    <div className={s.dropdownHeader}>
                      <div className={s.dropdownName}>{user.name || 'User'}</div>
                      <div className={s.dropdownEmail}>{user.email}</div>
                    </div>
                    <Link
                      to="/dashboard"
                      className={s.dropdownItem}
                      role="menuitem"
                      onClick={() => setOpen(false)}
                    >
                      📊 Dashboard
                    </Link>
                    <Link
                      to="/upload"
                      className={s.dropdownItem}
                      role="menuitem"
                      onClick={() => setOpen(false)}
                    >
                      📤 Upload video
                    </Link>
                    <button
                      className={`${s.dropdownItem} ${s.dropdownItemDanger}`}
                      role="menuitem"
                      onClick={handleLogout}
                    >
                      🚪 Sign out
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <Link to="/login"    className={`${s.authBtn} ${s.authBtnGhost}`}>Sign in</Link>
              <Link to="/register" className={`${s.authBtn} ${s.authBtnPrimary}`}>Get started</Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
