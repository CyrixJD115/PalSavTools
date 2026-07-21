<script lang="ts">
  // Inline modal for changing an item slot's stack count. Clones the
  // ContainerDetailModal shell (scrim + surface panel + header + actions).
  import Icon from '@iconify/svelte';
  import Button from '$components/ui/Button.svelte';
  import { peekItem, prettyItemId, itemIconUrl, imgOnError } from '$lib/utils/items';
  import { t } from '$stores/index';
  import type { ContainerItemSlot } from '$types/index';

  let {
    slot,
    onclose,
    onsubmit,
  }: {
    slot: ContainerItemSlot;
    onclose: () => void;
    onsubmit: (newCount: number) => Promise<void>;
  } = $props();

  // The modal is remounted fresh each time the parent opens it (toggled via
  // {#if setCountSlot}), so capturing slot.count as the initial $state value
  // is intentional — we don't want `value` to reactively reset if the prop
  // changes mid-edit.
  // svelte-ignore state_referenced_locally
  let value = $state(slot.count);
  let loading = $state(false);
  let error = $state<string | null>(null);

  const meta = $derived(peekItem(slot.static_id));
  const name = $derived(meta?.name || prettyItemId(slot.static_id));
  const maxStack = $derived(meta?.max_stack ?? 9999);

  async function submit() {
    if (value < 0 || value > 9999) {
      error = 'Count must be between 0 and 9999';
      return;
    }
    loading = true; error = null;
    try {
      await onsubmit(value);
      onclose();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()}
  role="dialog"
  tabindex="-1"
>
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-md w-full mx-4 overflow-hidden animate-scale-in"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2 min-w-0">
        {#if meta?.icon}
          <img
            src={itemIconUrl(meta.icon)}
            alt={name}
            class="w-8 h-8 object-contain rounded-2 bg-bg-deep border border-line/40 p-0.5"
            onerror={imgOnError}
          />
        {/if}
        <h2 class="text-base font-bold heading-gradient truncate">{name}</h2>
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast shrink-0" onclick={onclose}>
        <Icon icon="lucide:x" width={18} />
      </button>
    </div>

    <div class="p-4 space-y-3">
      <p class="text-xs text-ink-muted">
        {$t('web.inventory.set_count_hint', 'Set the stack count for this item. Enter 0 to clear the slot (the slot itself is kept).')}
      </p>

      <label class="block">
        <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
          {$t('web.inventory.count_label', 'Count')}
        </span>
        <input
          class="input w-full text-sm tabular-nums"
          type="number"
          min={0}
          max={9999}
          bind:value
          onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && submit()}
        />
        {#if meta?.max_stack}
          <span class="block text-[10px] text-ink-dim mt-1">Max stack: {maxStack}</span>
        {/if}
      </label>

      {#if error}
        <p class="text-xs text-status-error">{error}</p>
      {/if}

      <div class="flex justify-end gap-2 pt-1">
        <Button variant="ghost" onclick={onclose} disabled={loading}>
          {$t('web.common.cancel')}
        </Button>
        <Button variant="primary" onclick={submit} loading={loading}>
          {$t('web.common.set')}
        </Button>
      </div>
    </div>
  </div>
</div>
