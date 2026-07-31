import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,  // Enable WebSocket proxying
        proxyTimeout: 400000,  // 400s - longer than Ollama analysis (2-3 min)
        timeout: 400000,
      },
      '/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        proxyTimeout: 400000,
        timeout: 400000,
      },
      '/metrics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        proxyTimeout: 60000,
        timeout: 60000,
      },
    },
  },
})
