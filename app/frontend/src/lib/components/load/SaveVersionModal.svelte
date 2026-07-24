<script lang="ts">
  import { t } from '$stores/index';
  import Button from '$components/ui/Button.svelte';
  import Icon from '@iconify/svelte';

  let {
    open = $bindable(false),
    onchoose,
  }: {
    open: boolean;
    /** Called with true to continue loading, false to cancel/unload. */
    onchoose?: (continue_: boolean) => void;
  } = $props();

  function close(continue_: boolean) {
    open = false;
    onchoose?.(continue_);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close(false);
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" role="presentation">
    <div class="w-full max-w-lg card shadow-card-lg border-status-amber/40 border-2" role="dialog" aria-modal="true" aria-label="Save version warning">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:triangle-alert" width={18} class="text-status-amber" />
          {$t('web.save_version.title')}
        </h2>
        <button class="text-ink-dim hover:text-ink-primary transition-fast" onclick={() => close(false)} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <p class="text-sm text-ink-secondary mb-4">
        {$t('web.save_version.intro')}
      </p>

      <div class="bg-bg-hover border border-line rounded-6 p-3 mb-4 text-xs text-ink-muted leading-relaxed space-y-1.5">
        <div class="flex items-start gap-2">
          <Icon icon="lucide:info" width={14} class="text-status-amber shrink-0 mt-0.5" />
          <span>{$t('web.save_version.info_preupdate')}</span>
        </div>
        <div class="flex items-start gap-2">
          <Icon icon="lucide:sparkles" width={14} class="text-accent shrink-0 mt-0.5" />
          <span>{$t('web.save_version.info_postupdate')}</span>
        </div>
      </div>

      <p class="text-xs text-ink-dim mb-5">{$t('web.save_version.hint_strong')}</p>

      <div class="flex justify-end gap-2">
        <Button variant="ghost" onclick={() => close(false)}>{$t('web.save_version.cancel')}</Button>
        <Button variant="primary" onclick={() => close(true)}>{$t('web.save_version.continue')}</Button>
      </div>
    </div>
  </div>
{/if}