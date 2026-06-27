<script lang="ts">
  /**
   * MapContextMenu — right-click dropdown menu matching the PySide6 context
   * menus for bases, players, zones, and empty space.
   *
   * Appears at the cursor position. Dismissed on any outside click or Escape.
   */

  import { onMount, onDestroy } from 'svelte';
  import Icon from '@iconify/svelte';

  export interface MenuItem {
    label: string;
    icon?: string;
    action: () => void;
    danger?: boolean;
    separator?: boolean;
  }

  interface Props {
    items: MenuItem[];
    x: number;
    y: number;
    onclose: () => void;
  }

  let { items, x, y, onclose }: Props = $props();

  let menuX = $derived(Math.min(x, window.innerWidth - 220));
  let menuY = $derived(Math.min(y, window.innerHeight - items.length * 36 - 20));

  function handleAction(item: MenuItem) {
    item.action();
    onclose();
  }

  function handleWindowClick() {
    onclose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }

  onMount(() => {
    window.addEventListener('click', handleWindowClick);
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('click', handleWindowClick);
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

<div
  class="absolute z-50 min-w-[200px] rounded-6 border border-line/40 bg-bg-elevated/95 backdrop-blur-md shadow-2xl py-1"
  style="left: {menuX}px; top: {menuY}px;"
  role="menu"
  onkeydown={(e) => { if (e.key === 'Escape') e.stopPropagation(); }}
  onclick={(e) => e.stopPropagation()}
>
  {#each items as item}
    {#if item.separator}
      <div class="h-px bg-line/20 my-1"></div>
    {:else}
      <button
        class="flex items-center gap-2.5 w-full px-3 py-2 text-xs text-left transition-colors duration-100
               {item.danger
                 ? 'text-red-400 hover:bg-red-500/10'
                 : 'text-ink-secondary hover:bg-accent-cyan/10 hover:text-ink-primary'}"
        onclick={() => handleAction(item)}
      >
        {#if item.icon}
          <Icon icon={item.icon} width="14" class="shrink-0" />
        {/if}
        <span>{item.label}</span>
      </button>
    {/if}
  {/each}
</div>
