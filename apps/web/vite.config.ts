/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const apiProxy = process.env.VITE_API_PROXY ?? 'http://localhost:8000'
/** Color de la barra del sistema y del ícono instalado: maqui, la semilla del tema (igual en index.html). */
export const THEME_COLOR = '#6d2a57'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'favicon-64.png', 'apple-touch-icon.png', 'brand/*.svg'],
      manifest: {
        name: 'Cáterin',
        short_name: 'Cáterin',
        description: 'Gestión simple para tu negocio de catering',
        lang: 'es-CL',
        theme_color: THEME_COLOR,
        background_color: '#fff8f8',
        display: 'standalone',
        start_url: '/',
        // `any` con esquinas redondeadas y `maskable` aparte, con fondo completo y el dibujo en la zona segura.
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api\//, /^\/docs/],
        // Fuentes (solo woff2) e imágenes de la marca en el precaché: la app se ve igual sin red.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        // Logos y fotos del catálogo del portal (ADR-009): el nombre es el hash del contenido, así que una vez vistos
        // se sirven del caché, también sin red. Tope para no llenar el teléfono.
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/v1/portal/media/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'catalogo-imagenes',
              expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  server: { proxy: { '/api': apiProxy, '/docs': apiProxy } },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false, include: ['src/**/*.test.{ts,tsx}'] },
})
