import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const variant = env.VITE_VARIANT || mode;
  const ports: Record<string, number> = { user: 5173, vendor: 5174, admin: 5175 };
  const selectedPort = ports[variant] ?? 5173;
  return {
    build: {
      // Keep build output inside the frontend directory so Vercel can serve it
      outDir: variant ? `dist/${variant}` : 'dist',
      emptyOutDir: true,
    },
    server: {
      port: selectedPort,
      strictPort: true,
      host: '127.0.0.1',
    },
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      }
    },
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: [
          'icons/icon-192.png',
          'icons/icon-512.png',
          'icons/apple-touch-icon.png',
          'icons/maskable-512.png',
        ],
        manifest: {
          name: 'Skyro',
          short_name: 'Skyro',
          description: 'Skyro Campus Food Ordering',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          background_color: '#0b1220',
          theme_color: '#0b1220',
          icons: [
            {
              src: '/icons/icon-192.png',
              sizes: '192x192',
              type: 'image/png',
            },
            {
              src: '/icons/icon-512.png',
              sizes: '512x512',
              type: 'image/png',
            },
            {
              src: '/icons/maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },
        workbox: {
          navigateFallback: '/index.html',
          globPatterns: ['**/*.{js,css,html,ico,png,svg,json,woff2}'],
          runtimeCaching: [
            {
              urlPattern: ({ request }) => request.destination === 'image',
              handler: 'CacheFirst',
              options: {
                cacheName: 'images',
                expiration: {
                  maxEntries: 200,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
              },
            },
            {
              urlPattern: ({ request }) => request.destination === 'document',
              handler: 'NetworkFirst',
              options: {
                cacheName: 'pages',
              },
            },
          ],
        },
      }),
    ],
  };
});
