<script lang="ts">
  // N×M CSS grid of ItemSlots. Renders populated slots at their slot_index and
  // pads up to slot_count with empty placeholders so the grid always reflects
  // the container's capacity (matches the in-game inventory look).
  import ItemSlot from './ItemSlot.svelte';
  import ItemTooltip from './ItemTooltip.svelte';
  import type { ContainerItemSlot } from '$types/index';

  let {
    items,
    slotCount = 0,
    cols = 8,
    size = 'md',
    onclick,
    oncontextmenu,
  }: {
    items: ContainerItemSlot[];
    slotCount?: number;
    cols?: number;
    size?: 'sm' | 'md' | 'lg';
    onclick?: (slot: ContainerItemSlot) => void;
    oncontextmenu?: (slot: ContainerItemSlot, e: MouseEvent) => void;
  } = $props();

  // Index items by slot_index for O(1) lookup.
  const byIndex = $derived.by(() => {
    const m = new Map<number, ContainerItemSlot>();
    for (const it of items) m.set(it.slot_index, it);
    return m;
  });

  // The grid spans max(slotCount, max slot_index + 1, items.length) cells so we
  // never accidentally hide a slot whose index exceeds the declared capacity.
  const gridCells = $derived(
    Math.max(slotCount, ...items.map((i) => i.slot_index + 1), items.length, 0)
  );

  const cells = $derived(Array.from({ length: gridCells }, (_, i) => i));
</script>

<div
  class="grid gap-1.5 p-2 rounded-4 bg-bg-deep/30 border border-line/20"
  style="grid-template-columns: repeat({cols}, minmax(0, 1fr));"
>
  {#each cells as idx (idx)}
    {@const slot = byIndex.get(idx) ?? null}
    {@const isEmpty = !slot || slot.count <= 0 || !slot.static_id}
    <ItemSlot
      item={slot}
      empty={isEmpty}
      {size}
      {onclick}
      {oncontextmenu}
    >
      {#snippet tooltip(s: ContainerItemSlot)}
        <ItemTooltip item={s} />
      {/snippet}
    </ItemSlot>
  {/each}

  {#if gridCells === 0}
    <p class="col-span-full text-center text-xs text-ink-dim py-6">No slots allocated.</p>
  {/if}
</div>
