<script lang="ts">
  import { t } from '$stores/index';
  import type { StorageMode } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Icon from '@iconify/svelte';

  let {
    open = $bindable(false),
    fileSize = 0,
    threshold = 50,
    onchoose,
  }: {
    open: boolean;
    /** Upload file size in bytes (for display). */
    fileSize: number;
    /** Threshold in MB that triggered the warning. */
    threshold: number;
    /** Called with the chosen mode, or null if the user cancels. */
    onchoose?: (mode: StorageMode | null) => void;
  } = $props();

  function fmtMb(bytes: number): string {
    return (bytes / 1024 / 1024).toFixed(1);
  }

  function close(mode: StorageMode | null) {
    open = false;
    onchoose?.(mode);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close(null);
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" role="presentation">
    <div class="w-full max-w-lg card shadow-card-lg border-status-amber/40 border-2" role="dialog" aria-modal="true" aria-label="Large save — choose storage mode">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:triangle-alert" width={18} class="text-status-amber" />
          {$t('web.load_warning.title')}
        </h2>
        <button class="text-ink-dim hover:text-ink-primary transition-fast" onclick={() => close(null)} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <p class="text-sm text-ink-secondary mb-4">
        {$t('web.load_warning.intro', { size: fmtMb(fileSize), threshold: String(threshold) })}
      </p>

      <div class="space-y-3">
        <button
          type="button"
          class="w-full text-left rounded-6 border-2 bg-bg-deep p-4 transition-fast hover:border-accent/50 hover:bg-bg-hover
                 {$t('web.load_warning.memory_title') === 'Load in Memory' ? 'border-accent/40 bg-accent/5' : 'border-line'}"
          onclick={() => close('memory')}
        >
          <div class="flex items-start gap-3">
            <Icon icon="lucide:memory-stick" width={20} class="text-accent shrink-0 mt-0.5" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="text-sm font-semibold text-ink-emphasis">{$t('web.load_warning.memory_title')}</p>
                <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-accent/20 text-accent leading-tight">{$t('web.common.recommended')}</span>
              </div>
              <p class="text-xs text-ink-muted mt-1 leading-relaxed">{$t('web.load_warning.memory_desc')}</p>
            </div>
            <Icon icon="lucide:chevron-right" width={16} class="text-ink-dim shrink-0 mt-1" />
          </div>
        </button>

        <button
          type="button"
          class="w-full text-left rounded-6 border-2 border-line bg-bg-deep p-4 transition-fast hover:border-accent/50 hover:bg-bg-hover"
          onclick={() => close('disk')}
        >
          <div class="flex items-start gap-3">
            <Icon icon="lucide:hard-drive" width={20} class="text-accent shrink-0 mt-0.5" />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-ink-emphasis">{$t('web.load_warning.disk_title')}</p>
              <p class="text-xs text-ink-muted mt-1 leading-relaxed">{$t('web.load_warning.disk_desc')}</p>
            </div>
            <Icon icon="lucide:chevron-right" width={16} class="text-ink-dim shrink-0 mt-1" />
          </div>
        </button>
      </div>

      <div class="flex justify-between items-center mt-5">
        <p class="text-[10px] text-ink-dim">
          {$t('web.load_warning.remember_hint')}
        </p>
        <Button variant="ghost" onclick={() => close(null)}>{$t('web.common.cancel')}</Button>
      </div>
    </div>
  </div>
{/if}
