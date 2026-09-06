import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) return 'react'
          if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet')) return 'maps'
          if (id.includes('node_modules/recharts')) return 'charts'
          if (id.includes('node_modules')) return 'vendor'
        },
      },
    },
  },
  server: { host: true, port: 5173 },
  test: { environment: 'jsdom', globals: true, include: ['../tests/frontend/**/*.{test,spec}.jsx', '../tests/mesh/**/*.{test,spec}.js'] },
})
