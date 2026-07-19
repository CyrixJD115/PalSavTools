<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import type { Snippet } from 'svelte';
  import Sidebar from '$components/layout/Sidebar.svelte';
  import Header from '$components/layout/Header.svelte';
  import ToastContainer from '$components/ui/ToastContainer.svelte';
  import LoadingOverlay from '$components/ui/LoadingOverlay.svelte';
  import { api } from '$lib/api/client';
  import { getStoredLang } from '$lib/i18n.svelte';
  import {
    health, wsConnected, languages, currentLang, i18n, saveState, loadingSave, loadProgress,
  } from '$stores/index';
  import { syncFromHealth } from '$stores/settings';

  let { children }: { children: Snippet } = $props();
  let ws: WebSocket | null = null;

  onMount(() => {
    bootstrap();
    connectWs();
    return () => ws?.close();
  });

  async function bootstrap() {
    try {
      const h = await api.health();
      health.set(h);
      // Mirror the server's default storage threshold into the user-settings
      // store so the warning fires at the same cutoff on both sides (unless
      // the user has locally overridden it).
      syncFromHealth(h);
    } catch {
      health.set({ status: 'error', version: '?', app_version: '?', game_version: '?', save_loaded: false, storage_mode: 'memory', large_save_threshold_mb: 50 });
    }
    try {
      saveState.set(await api.saveState());
    } catch { /* ignore */ }
    try {
      const langs = await api.languages();
      languages.set(langs);
      // The i18n store is already seeded with the inline English catalog (see
      // stores/index.ts), so the app renders translated from first paint — no
      // FOUC. Here we only swap in the persisted language if it differs from
      // the seeded English default, avoiding a needless fetch on the common path.
      const stored = getStoredLang();
      const known = stored && langs.available.some((l) => l.code === stored);
      const lang = known ? stored! : langs.current;
      currentLang.set(lang);
      if (lang !== 'en_US') {
        const res = await api.i18n(lang);
        i18n.set(res.keys);
      }
    } catch { /* ignore - i18n is non-fatal */ }
  }

  function connectWs() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
      const socket = new WebSocket(`${proto}//${location.host}/ws`);
      socket.onopen = () => wsConnected.set(true);
      socket.onclose = () => wsConnected.set(false);
      socket.onerror = () => wsConnected.set(false);
      socket.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'save_state' || data.type === 'save_update') {
            saveState.set(await api.saveState());
          } else if (data.type === 'load_progress') {
            const payload = data.payload as { stage: string; current: number; total: number; section: string | null };
            loadProgress.set(payload);
            // On the terminal stage, clear progress after a short beat so the
            // overlay can fade back to its resting state.
            if (payload.stage === 'done') {
              setTimeout(() => loadProgress.set(null), 400);
            }
          }
        } catch { /* ignore malformed */ }
      };
      ws = socket;
    } catch {
      wsConnected.set(false);
    }
  }
</script>

<div class="flex h-screen overflow-hidden relative z-[1]">
  <Sidebar />
  <div class="flex-1 flex flex-col overflow-hidden">
    <Header />
    <main class="flex-1 overflow-y-auto {$page.url.pathname === '/map' ? '' : ''}">
      {@render children()}
    </main>
  </div>
</div>

<div class="fixed inset-0 pointer-events-none z-0"
  style="  background: url('/bg-corner.png') no-repeat bottom right / 880px auto; opacity: 0.50;">
</div>

<LoadingOverlay open={$loadingSave} />

<ToastContainer />
