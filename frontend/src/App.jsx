import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from '@/components/ProtectedRoute'
import Navbar from '@/components/Navbar'

// Pages — filled in per module
import LoginPage    from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import HomePage     from '@/pages/HomePage'
import BrowsePage   from '@/pages/BrowsePage'
import PlayerPage   from '@/pages/PlayerPage'
import UploadPage   from '@/pages/UploadPage'
import DashboardPage from '@/pages/DashboardPage'

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        {/* Public routes */}
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/"            element={<HomePage />} />
          <Route path="/browse"      element={<BrowsePage />} />
          <Route path="/videos/:id"  element={<PlayerPage />} />
          <Route path="/upload"      element={<UploadPage />} />
          <Route path="/dashboard"   element={<DashboardPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
