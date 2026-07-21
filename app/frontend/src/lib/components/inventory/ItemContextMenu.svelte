<script lang="ts">
  // Right-click context menu for an item slot. Rendered at the cursor position
  // over a scrim that closes the menu on outside click / Escape.
  //
  // Actions: Set Count…, Delete Item, Copy Item ID. The parent wires each to
  // the appropriate API call + refetch.
  import Icon from '@iconify/svelte';
  import type { ContainerItemSlot } from '$types/index';

  let {
    slot,
    x,
    y,
    onclose,
    onsetcount,
    ondelete,
  }: {
    slot: ContainerItemSlot;
    x: number;
    y: number;
    onclose: () => void;
    onsetcount: (slot: ContainerItemSlot) => void;
    ondelete: (slot: ContainerItemSlot) => void;
  } = $props();

  // Keep the menu inside the viewport.
  const menuW = 180;
  const menuH = 132;
  const adjustedX = $derived(Math.min(x, (typeof window !== 'undefined' ? window.innerWidth : 9999) - menuW - 8));
  const adjustedY = $derived(Math.min(y, (typeof window !== 'undefined' ? window.innerHeight : 9999) - menuH - 8));

  async function copyId() {
    try {
      await navigator.clipboard.writeText(slot.static_id);
    } catch { /* clipboard may be blocked — silent */ }
    onclose();
  }

  function pickSetCount() { onsetcount(slot); onclose(); }
  function pickDelete() { ondelete(slot); onclose(); }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class="fixed inset-0 z-50"
  onclick={onclose}
  oncontextmenu={(e: MouseEvent) => { e.preventDefault(); onclose(); }}
  onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()}
>
  <div
    class="absolute bg-bg-surface border border-line/60 rounded-6 shadow-xl py-1 w-44 text-sm animate-scale-in"
    style="left: {adjustedX}px; top: {adjustedY}px;"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={(e: KeyboardEvent) => e.stopPropagation()}
    role="menu"
    tabindex={-1}
  >
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-ink-primary hover:bg-bg-hover transition-fast"
      onclick={pickSetCount}
      role="menuitem"
    >
      <Icon icon="lucide:hash" width={14} class="text-ink-muted" />
      Set Count…
    </button>
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-status-error hover:bg-status-error/10 transition-fast"
      onclick={pickDelete}
      role="menuitem"
    >
      <Icon icon="lucide:trash-2" width={14} />
      Delete Item
    </button>
    <div class="my-1 border-t border-line/30"></div>
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-ink-secondary hover:bg-bg-hover transition-fast"
      onclick={copyId}
      role="menuitem"
    >
      <Icon icon="lucide:copy" width={14} class="text-ink-muted" />
      Copy Item ID
    </button>
  </div>
</div>
