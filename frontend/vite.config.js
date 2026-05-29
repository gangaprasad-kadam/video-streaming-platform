import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  server: {
    port: 5173,
    proxy: {
      // Dev proxy: forward API calls to NGINX/backend on port 80
      '/auth':      { target: 'http://localhost', changeOrigin: true },
      '/users':     { target: 'http://localhost', changeOrigin: true },
      '/videos':    { target: 'http://localhost', changeOrigin: true },
      '/stream':    { target: 'http://localhost', changeOrigin: true },
      '/summary':   { target: 'http://localhost', changeOrigin: true },
      '/trending':  { target: 'http://localhost', changeOrigin: true },
      // /trending/recommendations/* is covered by the /trending proxy above
      '/events':    { target: 'http://localhost', changeOrigin: true },
      '/heatmap':   { target: 'http://localhost', changeOrigin: true },
    },
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**'],
      exclude: ['src/main.jsx'],
    },
  },
})
