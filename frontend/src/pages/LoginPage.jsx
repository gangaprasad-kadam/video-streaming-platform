import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import s from '@/styles/auth.module.css'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate   = useNavigate()

  const [form,    setForm]    = useState({ email: '', password: '' })
  const [errors,  setErrors]  = useState({})
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)

  const validate = () => {
    const e = {}
    if (!form.email)    e.email    = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Enter a valid email'
    if (!form.password) e.password = 'Password is required'
    return e
  }

  const handleChange = (field) => (e) => {
    setForm((f) => ({ ...f, [field]: e.target.value }))
    if (errors[field]) setErrors((prev) => { const n = { ...prev }; delete n[field]; return n })
    setApiError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const fieldErrors = validate()
    if (Object.keys(fieldErrors).length) { setErrors(fieldErrors); return }
    setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/', { replace: true })
    } catch (err) {
      setApiError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={s.page}>
      <div className={s.card}>
        <div className={s.brand}>
          <div className={s.brandIcon}>▶</div>
          <span className={s.brandName}>VidStream</span>
        </div>

        <h1 className={s.heading}>Welcome back</h1>
        <p className={s.subheading}>Sign in to continue watching</p>

        {apiError && <div className={s.errorAlert}>{apiError}</div>}

        <form className={s.form} onSubmit={handleSubmit} noValidate>
          <div className={s.field}>
            <label className={s.label} htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className={`${s.input} ${errors.email ? s.inputError : ''}`}
              placeholder="you@example.com"
              value={form.email}
              onChange={handleChange('email')}
              autoComplete="email"
            />
            {errors.email && <span className={s.fieldError}>{errors.email}</span>}
          </div>

          <div className={s.field}>
            <label className={s.label} htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className={`${s.input} ${errors.password ? s.inputError : ''}`}
              placeholder="••••••••"
              value={form.password}
              onChange={handleChange('password')}
              autoComplete="current-password"
            />
            {errors.password && <span className={s.fieldError}>{errors.password}</span>}
          </div>

          <button type="submit" className={s.btn} disabled={loading}>
            {loading ? <span className="spinner" /> : null}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className={s.footer}>
          Don&apos;t have an account?{' '}
          <Link to="/register" className={s.link}>Create one</Link>
        </p>
      </div>
    </div>
  )
}
