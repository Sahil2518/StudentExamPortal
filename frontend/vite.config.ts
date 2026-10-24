import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vite configuration for the AI Adaptive Exam Portal.
//
// Development proxy: API calls to /api/* are forwarded to the backend
// at http://127.0.0.1:8000 so you can use relative URLs in development
// without CORS issues. In production, set VITE_API_URL in your env.
//
// Code splitting: vendor libraries (React, Recharts, Router) are split
// into their own chunk so the main app bundle stays small and browsers
// can cache the vendor chunk across deployments.

export default defineConfig({
  plugins: [react()],
  
  test: {
    environment: 'jsdom',
    globals: true,
  },

  server: {
    port: 5173,
    // Proxy API calls from the frontend dev server to the backend
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },

  build: {
    // Raise the warning threshold slightly since recharts is legitimately large
    chunkSizeWarningLimit: 700,

    rollupOptions: {
      output: {
        // Split vendor libraries into a separate cached chunk
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
        },
      },
    },
  },
})
