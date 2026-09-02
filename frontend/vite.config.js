import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config for Razor-AI React frontend
// Proxies /api requests to the FastAPI backend running on port 8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    // Proxy API calls to FastAPI backend to avoid CORS issues in dev
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
