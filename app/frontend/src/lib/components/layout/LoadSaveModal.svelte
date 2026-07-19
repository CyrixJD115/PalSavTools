<script lang="ts">
  import { api } from '$lib/api/client';
  import { saveState, loadingSave, loadError, t } from '$stores/index';
  import { settings } from '$stores/settings';
  import { toast } from '$stores/toast';
  import Button from '$components/ui/Button.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import Icon from '@iconify/svelte';
  import { get } from 'svelte/store';

  let { open = $bindable(false) }: { open: boolean } = $props();

  let path = $state('');
  let busy = $state(false);

  function close() {
    if (!busy) open = false;
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }

  async function doLoad() {
    const p = path.trim();
    if (!p) return;
    busy = true;
    loadingSave.set(true);
    loadError.set(null);
    try {
      // Path-load: no pre-flight file size, so honor the persisted preference
      // instead of popping the size-based warning (which only fires on the
      // browser upload path where bytes are already in hand).
      const s = get(settings);
      const res = await api.loadFromPath(p, {
        storageMode: s.storageMode,
        prewarm: s.prewarm,
      });
      saveState.set({ loaded: true, summary: res.summary, counts: res.counts });
      toast.success($t('web.toast.loaded', { filename: res.summary.filename, guilds: res.counts.guilds, players: res.counts.players }));
      open = false;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      loadError.set(msg);
      toast.error($t('web.toast.load_failed_msg', { msg }));
    } finally {
      busy = false;
      loadingSave.set(false);
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" role="presentation">
    <div class="w-full max-w-lg card shadow-card-lg border-accent/40 border-2" role="dialog" aria-modal="true" aria-label="Load save">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:folder-open" width={18} class="text-accent" /> {$t('web.load_modal.title')}
        </h2>
        <button class="text-ink-dim hover:text-ink-primary" onclick={close} disabled={busy} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <label for="save-path" class="block text-xs font-medium text-ink-secondary mb-1.5">
        {$t('web.load_modal.path_label')}
      </label>
      <input
        id="save-path"
        class="input font-mono text-xs"
        placeholder={$t('web.load_modal.path_placeholder')}
        bind:value={path}
        onkeydown={(e) => e.key === 'Enter' && doLoad()}
      />
      <p class="mt-2 text-xs text-ink-muted">
        {$t('web.load_modal.path_hint')}
      </p>

      {#if $loadError}
        <p class="mt-3 text-xs text-status-error bg-status-error/10 border border-status-error/30 rounded-6 p-2">
          {$loadError}
        </p>
      {/if}

      <div class="flex justify-end gap-2 mt-5">
        <Button variant="ghost" onclick={close} disabled={busy}>{$t('web.common.cancel')}</Button>
        <Button variant="primary" onclick={doLoad} disabled={busy || !path.trim()}>
          {#if busy}<Spinner size={14} />{/if}
          {$t('web.load_modal.load')}
        </Button>
      </div>
    </div>
  </div>
{/if}
