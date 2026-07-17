<script lang="ts">
  import { health, t } from '$stores/index';
  import Icon from '@iconify/svelte';

  let { open = $bindable(false) }: { open: boolean } = $props();

  let h = $derived($health);
  const ver = $derived(h?.game_version ?? '?');

  function close() { open = false; }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" role="presentation">
    <div class="w-full max-w-lg card shadow-card-lg border-status-amber/40 border-2" role="dialog" aria-modal="true" aria-label="Warnings">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:triangle-alert" width={18} class="text-status-amber" /> {$t('web.warning.title')}
        </h2>
        <button class="text-ink-dim hover:text-ink-primary transition-fast" onclick={close} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <div class="space-y-4">
        <div class="rounded-6 bg-status-amber/10 border-2 border-status-amber/25 p-4">
          <div class="flex items-start gap-3">
            <Icon icon="lucide:triangle-alert" width={20} class="text-status-amber shrink-0 mt-0.5" />
            <p class="text-sm text-status-amber font-semibold">
              {$t('web.warning.always_backup')}
            </p>
          </div>
        </div>

        <div class="rounded-6 bg-status-amber/10 border-2 border-status-amber/25 p-4">
          <div class="flex items-start gap-3">
            <Icon icon="lucide:refresh-cw" width={20} class="text-status-amber shrink-0 mt-0.5" />
            <p class="text-sm text-status-amber font-semibold">
              {$t('web.warning.update_after_patch', { game_version: ver })}
            </p>
          </div>
        </div>

        <div class="rounded-6 bg-status-error/10 border-2 border-status-error/25 p-4">
          <div class="flex items-start gap-3">
            <Icon icon="lucide:circle-x" width={20} class="text-status-error shrink-0 mt-0.5" />
            <p class="text-sm text-status-error font-semibold">
              {$t('web.warning.update_consequence')}
            </p>
          </div>
        </div>
      </div>

      <div class="flex justify-end mt-5">
        <button onclick={close} class="btn btn-warning">{$t('web.warning.understand')}</button>
      </div>
    </div>
  </div>
{/if}
