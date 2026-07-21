<script lang="ts">
  // Tab strip for switching between inventory bags. Mirrors the breeding-page
  // tab idiom: active = bg-accent/15 text-accent border-accent/40; inactive
  // = text-ink-secondary hover:bg-bg-hover border-transparent.
  //
  // Each tab shows a label + item-count badge. Clicking a tab fires onchange.
  import Icon from '@iconify/svelte';
  import type { InventoryBag } from '$types/index';

  let {
    bags,
    active,
    onchange,
  }: {
    bags: InventoryBag[];
    active: string;
    onchange: (bagType: string) => void;
  } = $props();

  const TAB_ICONS: Record<string, string> = {
    common:    'lucide:backpack',
    essential: 'lucide:key-round',
    weapon:    'lucide:sword',
    armor:     'lucide:shirt',
    food:      'lucide:utensils',
    drop:      'lucide:package-open',
  };
</script>

<div class="flex gap-1 flex-wrap border-b border-line/30 pb-2">
  {#each bags as bag (bag.bag_type)}
    {@const isActive = bag.bag_type === active}
    <button
      type="button"
      class="flex items-center gap-1.5 px-3 py-1.5 rounded-4 text-xs font-medium border transition-fast
        {isActive
          ? 'bg-accent/15 text-accent border-accent/40'
          : 'text-ink-secondary hover:bg-bg-hover border-transparent'}"
      onclick={() => onchange(bag.bag_type)}
      aria-pressed={isActive}
    >
      <Icon icon={TAB_ICONS[bag.bag_type] ?? 'lucide:package'} width={13} />
      <span>{bag.label}</span>
      {#if bag.item_count > 0}
        <span class="ml-0.5 px-1.5 py-px rounded-full text-[9px] tabular-nums
          {isActive ? 'bg-accent/30 text-accent-light' : 'bg-bg-elevated text-ink-muted'}">
          {bag.item_count}
        </span>
      {/if}
      {#if !bag.container_id}
        <span class="w-1.5 h-1.5 rounded-full bg-ink-dim/40" title="Not allocated"></span>
      {/if}
    </button>
  {/each}
</div>
