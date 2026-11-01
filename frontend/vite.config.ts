import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    port: 5173,
    // En desarrollo la API se sirve por el mismo origen para que la cookie HttpOnly funcione.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        // Separa las librerías pesadas para que el bundle inicial sea pequeño y cacheable.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('react-router')) return 'router'
          if (id.includes('radix-ui') || id.includes('@radix-ui')) return 'radix'
          if (id.includes('react-hook-form') || id.includes('zod') || id.includes('@hookform'))
            return 'forms'
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('scheduler'))
            return 'react'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    testTimeout: 15_000,
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/main.tsx',
        'src/**/*.test.{ts,tsx}',
        'src/components/ui/**',
        'src/vite-env.d.ts',
      ],
    },
  },
})
