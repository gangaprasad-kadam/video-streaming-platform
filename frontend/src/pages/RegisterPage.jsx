import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import s from '@/styles/auth.module.css'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate     = useNavigate()

  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [errors,   setErrors]   = useState({})
  const [apiError, setApiError] = useState('')
  const [loading,  setLoading]  = useState(false)

  const validate = () => {
    const e = {}
    if (!form.name.trim())  e.name     = 'Name is required'
    if (!form.email)        e.email    = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Enter a valid email'
    if (!form.password)     e.password = 'Password is required'
    else if (form.password.length < 8) e.password = 'Minimum 8 characters'
    if (form.password !== form.confirm) e.confirm = 'Passwords do not match'
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
      await register(form.name, form.email, form.password)
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

        <h1 className={s.heading}>Create account</h1>
        <p className={s.subheading}>Join VidStream and start watching</p>

        {apiError && <div className={s.errorAlert}>{apiError}</div>}

        <form className={s.form} onSubmit={handleSubmit} noValidate>
          <div className={s.field}>
            <label className={s.label} htmlFor="name">Full name</label>
            <input
              id="name"
              type="text"
              className={`${s.input} ${errors.name ? s.inputError : ''}`}
              placeholder="Jane Smith"
              value={form.name}
              onChange={handleChange('name')}
              autoComplete="name"
            />
            {errors.name && <span className={s.fieldError}>{errors.name}</span>}
          </div>

          <div className={s.field}>
            <label className={s.label} htmlFor="reg-email">Email</label>
            <input
              id="reg-email"
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
            <label className={s.label} htmlFor="reg-password">Password</label>
            <input
              id="reg-password"
              type="password"
              className={`${s.input} ${errors.password ? s.inputError : ''}`}
              placeholder="At least 6 characters"
              value={form.password}
              onChange={handleChange('password')}
              autoComplete="new-password"
            />
            {errors.password && <span className={s.fieldError}>{errors.password}</span>}
          </div>

          <div className={s.field}>
            <label className={s.label} htmlFor="confirm">Confirm password</label>
            <input
              id="confirm"
              type="password"
              className={`${s.input} ${errors.confirm ? s.inputError : ''}`}
              placeholder="••••••••"
              value={form.confirm}
              onChange={handleChange('confirm')}
              autoComplete="new-password"
            />
            {errors.confirm && <span className={s.fieldError}>{errors.confirm}</span>}
          </div>

          <button type="submit" className={s.btn} disabled={loading}>
            {loading ? <span className="spinner" /> : null}
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className={s.footer}>
          Already have an account?{' '}
          <Link to="/login" className={s.link}>Sign in</Link>
        </p>
      </div>
    </div>
  )
}
