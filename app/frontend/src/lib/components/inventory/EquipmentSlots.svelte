<script lang="ts">
  // Compact equipment panel — shows only the item slots that are actually
  // populated (no placeholders for empty slots). Each slot renders a small
  // tile with a slot label (Head, Body, Shield, etc.) and the item via
  // ItemTooltip on hover.
  //
  // Slot index conventions (confirmed against real saves):
  //   armor[0]=head  armor[1]=body  armor[2,3]=accessory1,2
  //   armor[4]=shield armor[5]=glider
  //   weapon[0..5]=weapon1..6   food[0..4]=food1..5
  import Icon from '@iconify/svelte';
  import ItemSlot from './ItemSlot.svelte';
  import ItemTooltip from './ItemTooltip.svelte';
  import { t } from '$stores/index';
  import type { ContainerItemSlot, InventoryBag } from '$types/index';

  let {
    armorBag,
    weaponBag,
    foodBag,
    onclick,
    oncontextmenu,
  }: {
    armorBag?: InventoryBag | null;
    weaponBag?: InventoryBag | null;
    foodBag?: InventoryBag | null;
    onclick?: (slot: ContainerItemSlot) => void;
    oncontextmenu?: (slot: ContainerItemSlot, e: MouseEvent) => void;
  } = $props();

  /** True when none of the equipment bags have a container_id — indicates the
   *  player's .sav couldn't be read or lacks InventoryInfo (missing file,
   *  host-save, different save version, etc.). */
  const noBagsAllocated = $derived(
    (!armorBag || !armorBag.container_id) &&
    (!weaponBag || !weaponBag.container_id) &&
    (!foodBag || !foodBag.container_id)
  );

  /** True when the bags exist but all have 0 items — the .sav was decoded and
   *  InventoryInfo was found, but the equipment slots are genuinely empty. */
  const hasBagsButEmpty = $derived(
    !noBagsAllocated &&
    (armorBag?.item_count ?? 0) === 0 &&
    (weaponBag?.item_count ?? 0) === 0 &&
    (foodBag?.item_count ?? 0) === 0
  );

  /** Collect every populated equipment slot into a flat display list.
   *  Empty slots are skipped entirely — no placeholders. */
  const equipped = $derived.by<{ slot: ContainerItemSlot; label: string; code: string }[]>(() => {
    const out: { slot: ContainerItemSlot; label: string; code: string }[] = [];

    function collect(bag: InventoryBag | null | undefined, idx: number, label: string, code: string) {
      if (!bag?.items) return;
      const found = bag.items.find((s) => s.slot_index === idx && s.count > 0 && s.static_id);
      if (found) out.push({ slot: found, label, code });
    }

    // Weapon loadout (slots 0-5)
    for (let i = 0; i < 6; i++) collect(weaponBag, i, 'Weapon', `W${i + 1}`);
    // Armor: head, body, shield, glider
    collect(armorBag, 0, $t('web.inventory.slot_head', 'Head'), 'H');
    collect(armorBag, 1, $t('web.inventory.slot_body', 'Body'), 'B');
    collect(armorBag, 4, $t('web.inventory.slot_shield', 'Shield'), 'S');
    collect(armorBag, 5, $t('web.inventory.slot_glider', 'Glider'), 'G');
    // Accessories (indices 2, 3, 6, 7)
    for (const idx of [2, 3, 6, 7]) collect(armorBag, idx, $t('web.inventory.slot_accessory', 'Accessory'), 'A');
    // Sphere module (index 8)
    collect(armorBag, 8, $t('web.inventory.slot_sphere_mod', 'Module'), 'SM');
    // Food slots
    for (let i = 0; i < 5; i++) collect(foodBag, i, $t('web.inventory.slot_food', 'Food'), `F${i + 1}`);

    return out;
  });
</script>

<div class="space-y-2">
  <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim flex items-center gap-1.5">
    <Icon icon="lucide:shield-half" width={11} />
    {$t('web.inventory.equipment_label', 'Equipment')}
    {#if equipped.length > 0}
      <span class="text-ink-muted normal-case tracking-normal text-[10px] font-normal">({equipped.length})</span>
    {/if}
  </p>

  {#if equipped.length === 0}
    {#if noBagsAllocated}
      <!-- diagnostic banner: .sav missing or no InventoryInfo -->
      <div class="flex items-start gap-2 p-2.5 rounded-4 bg-amber-500/10 border border-amber-500/30">
        <Icon icon="lucide:alert-triangle" width={14} class="text-amber-400 shrink-0 mt-0.5" />
        <div class="min-w-0">
          <p class="text-xs text-amber-300 font-medium leading-snug">
            {$t('web.inventory.equipment_no_bags_title', 'No inventory bags allocated')}
          </p>
          <p class="text-[10px] text-ink-muted leading-snug mt-0.5">
            {$t('web.inventory.equipment_no_bags_body', "This player's .sav file is missing or couldn't be decoded (common for host-only saves, Xbox Game Pass imports, or players who haven't logged in recently). Stats and tech-tree data may still be available from the world save.")}
          </p>
        </div>
      </div>
    {:else if hasBagsButEmpty}
      <p class="text-xs text-ink-dim italic">{$t('web.inventory.equipment_empty', 'Equipment slots allocated but none are populated.')}</p>
    {:else}
      <p class="text-xs text-ink-dim italic">{$t('web.inventory.equipment_empty', 'No items equipped.')}</p>
    {/if}
  {:else}
    <div class="flex flex-wrap gap-1.5">
      {#each equipped as eq (eq.code + eq.slot.slot_index)}
        <div class="flex items-center gap-1 px-1.5 py-1 rounded-4 bg-bg-deep/50 border border-line/30">
          <ItemSlot item={eq.slot} empty={false} size="sm" {onclick} {oncontextmenu}>
            {#snippet tooltip(s: ContainerItemSlot)}
              <ItemTooltip item={s} />
            {/snippet}
          </ItemSlot>
          <div class="min-w-0 max-w-[7rem]">
            <p class="text-[10px] text-ink-secondary leading-tight truncate font-medium">{eq.label}</p>
            <p class="text-[8px] text-ink-muted leading-tight truncate font-mono">{eq.slot.static_id}</p>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
