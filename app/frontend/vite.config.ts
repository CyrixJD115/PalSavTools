import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// In dev, proxy /api and /ws to the FastAPI backend (default :16921).
// @ts-ignore - process is injected by Vite at build time; @types/node not needed.
const BACKEND = process.env.PST_BACKEND_URL ?? 'http://127.0.0.1:16921';

// Repo root (app/frontend/ → ../..). Used so the i18n catalog JSON at
// <repo>/src/_resources/i18n_web/ can be imported into the bundle, baking the
// default English strings in at build time (anti-FOUC: the store is never empty).
const repoRoot = new URL('../../', import.meta.url).pathname;

export default defineConfig({
  plugins: [sveltekit()],
  resolve: {
    alias: {
      // Lets `import 'i18n-default/en_US.json'` resolve to the repo catalog.
      'i18n-default': `${repoRoot}src/_resources/i18n_web`,
    },
  },
  server: {
    port: 16920,
    fs: { allow: [repoRoot] },
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/assets': { target: BACKEND, changeOrigin: true },
      '/game-icons': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND.replace('http', 'ws'), ws: true },
    },
  },
});
