import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// Repo root (app/frontend/ → ../..). The i18n default catalog lives outside
// the frontend tree at <repo>/src/_resources/i18n_web/ — aliasing it here lets
// the store import the English JSON at build time (anti-FOUC: the store seeds
// with real translations before first paint).
const repoRoot = fileURLToPath(new URL('../../', import.meta.url));

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ fallback: 'index.html', strict: false }),
    alias: {
      '$lib': './src/lib',
      '$components': './src/lib/components',
      '$stores': './src/stores',
      '$types': './src/types',
      // Bakes <repo>/src/_resources/i18n_web/en_US.json into the bundle so the
      // i18n store is seeded with English before the first network fetch.
      'i18n-default': `${repoRoot}src/_resources/i18n_web`,
    },
  },
};

export default config;
