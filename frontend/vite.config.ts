import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/tg-crypto-pay/',
  plugins: [react()],
  build: {
    outDir: '../docs'
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8123',
        changeOrigin: true,
      }
    }
  }
})