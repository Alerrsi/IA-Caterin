/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const apiProxy = process.env.VITE_API_PROXY ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Cáterin',
        short_name: 'Cáterin',
        description: 'Gestión simple para tu negocio de catering',
        lang: 'es-CL',
        theme_color: '#3d4449',
        background_color: '#f8f9fa',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
      },
      workbox: { navigateFallbackDenylist: [/^\/api\//, /^\/docs/] },
    }),
  ],
  server: { proxy: { '/api': apiProxy, '/docs': apiProxy } },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false, include: ['src/**/*.test.{ts,tsx}'] },
})
