<script lang="ts">
  // Full PSP-style hover popup for an item slot. Mirrors PSP's ItemBadge popup:
  // rarity-colored header, large icon, count box, description, combat stats
  // (atk/def for weapons/armor), durability bar (color-coded), weight, and
  // passive-skill chips for weapons/eggs.
  import {
    peekItem, prettyItemId, itemIconUrl, imgOnError, rarityInfo,
  } from '$lib/utils/items';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';
  import type { ContainerItemSlot, DynamicItemDetail } from '$types/index';

  let { item }: { item: ContainerItemSlot } = $props();

  const meta = $derived(peekItem(item.static_id));
  const name = $derived(meta?.name || prettyItemId(item.static_id));
  const dyn = $derived(item.dynamic);
  const rarity = $derived(rarityInfo(meta?.rarity ?? 0));

  // Durability as a 0-100 percentage of the DB-listed max.
  const durPct = $derived.by(() => {
    if (!dyn?.durability || !meta?.durability) return null;
    const max = meta.durability;
    if (max <= 0) return null;
    return Math.max(0, Math.min(100, (dyn.durability / max) * 100));
  });
  const durColor = $derived(
    durPct === null ? '' :
    durPct > 60 ? 'bg-status-success' :
    durPct > 25 ? 'bg-status-warning' : 'bg-status-error'
  );

  // Total weight (per-unit × count).
  const totalWeight = $derived(
    meta?.weight != null ? (meta.weight * item.count).toFixed(1) : null
  );

  // Whether to show combat stats (only for weapons/armor).
  const isWeapon = $derived(dyn?.type === 'weapon' || meta?.type_a_display === 'Weapon');
  const isArmor = $derived(dyn?.type === 'armor' ||
    meta?.type_a_display === 'Armor' || meta?.type_a_display === 'Accessory');
  const isFood = $derived(meta?.type_a_display === 'Food' || meta?.restore_satiety != null);

  // Stat rows for the combat-stats footer.
  const statRows = $derived.by(() => {
    const rows: { label: string; value: number; icon: string }[] = [];
    if (isWeapon) {
      if (meta?.physical_atk) rows.push({ label: 'Phys. ATK', value: meta.physical_atk, icon: 'lucide:sword' });
      if (meta?.magic_atk) rows.push({ label: 'Magic ATK', value: meta.magic_atk, icon: 'lucide:wand-2' });
      if (meta?.magazine_size) rows.push({ label: 'Magazine', value: meta.magazine_size, icon: 'lucide:circle-dot' });
      if (meta?.sneak_atk_rate) rows.push({ label: 'Sneak %', value: meta.sneak_atk_rate, icon: 'lucide:eye-off' });
    }
    if (isArmor) {
      if (meta?.physical_def) rows.push({ label: 'Phys. DEF', value: meta.physical_def, icon: 'lucide:shield' });
      if (meta?.magic_def) rows.push({ label: 'Magic DEF', value: meta.magic_def, icon: 'lucide:sparkles' });
      if (meta?.hp_value) rows.push({ label: 'HP', value: meta.hp_value, icon: 'lucide:heart' });
      if (meta?.shield_value) rows.push({ label: 'Shield', value: meta.shield_value, icon: 'lucide:shield-plus' });
    }
    if (isFood) {
      if (meta?.restore_satiety) rows.push({ label: 'Satiety', value: meta.restore_satiety, icon: 'lucide:utensils' });
      if (meta?.restore_sanity) rows.push({ label: 'Sanity', value: meta.restore_sanity, icon: 'lucide:brain' });
      if (meta?.restore_health) rows.push({ label: 'Health', value: meta.restore_health, icon: 'lucide:heart-pulse' });
    }
    return rows;
  });

  const VARIANT_LABEL: Record<DynamicItemDetail['type'], string> = {
    weapon: 'Weapon', armor: 'Armor', egg: 'Pal Egg', unknown: 'Dynamic',
  };
  const VARIANT_ICON: Record<DynamicItemDetail['type'], string> = {
    weapon: 'lucide:sword', armor: 'lucide:shirt', egg: 'lucide:egg', unknown: 'lucide:help-circle',
  };
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="w-72 bg-bg-surface border border-line/40 rounded-6 shadow-xl overflow-hidden pointer-events-none">
  <!-- header: rarity-colored bar with name + type/rarity badges -->
  <div class="px-3 py-2 border-b {rarity.headerClass}">
    <div class="flex items-center gap-2">
      {#if isWeapon || isArmor}
        <Icon icon={VARIANT_ICON[dyn?.type ?? (isWeapon ? 'weapon' : 'armor')]} width={14} class="shrink-0" />
      {/if}
      <h4 class="font-bold text-sm leading-tight truncate flex-1">{name}</h4>
      {#if meta?.rarity}
        <span class="text-[10px] font-bold px-1.5 py-px rounded-2 border {rarity.badgeClass}">{rarity.name}</span>
      {/if}
    </div>
    {#if meta?.type_a_display || dyn}
      <p class="text-[10px] opacity-80 mt-0.5">
        {meta?.type_a_display || VARIANT_LABEL[dyn!.type]}
        {#if meta?.type_b_display}· {meta.type_b_display}{/if}
      </p>
    {/if}
  </div>

  <!-- body: large icon + count box -->
  <div class="flex items-stretch bg-bg-deep/40">
    <div class="p-3 shrink-0">
      {#if meta?.icon}
        <img
          src={itemIconUrl(meta.icon)}
          alt={name}
          class="w-20 h-20 object-contain"
          onerror={imgOnError}
        />
      {:else}
        <div class="w-20 h-20 flex items-center justify-center text-ink-dim">
          <Icon icon="lucide:package" width={36} />
        </div>
      {/if}
    </div>
    <div class="flex-1 flex flex-col justify-between py-2 pr-3 min-w-0">
      <!-- count box -->
      <div class="self-end flex items-center gap-1.5 px-2 py-1 rounded-4 bg-bg-elevated border border-line/40">
        <Icon icon="lucide:package" width={11} class="text-ink-muted" />
        <span class="text-xs text-ink-muted">In Inventory:</span>
        <span class="text-sm font-bold text-ink-primary tabular-nums">{item.count}</span>
      </div>
      {#if dyn?.type === 'egg' && dyn.character_id}
        <div class="self-end flex items-center gap-1.5 mt-1">
          <Icon icon="lucide:paw-print" width={11} class="text-amber-400" />
          <span class="text-[11px] text-amber-300 font-medium">{dyn.character_id.replace(/_/g, ' ')}</span>
        </div>
      {/if}
    </div>
  </div>

  <!-- description -->
  {#if meta?.description}
    <div class="px-3 py-2 bg-bg-deep/20 border-t border-line/20">
      <p class="text-[11px] text-ink-muted leading-snug whitespace-pre-line line-clamp-4">{meta.description}</p>
    </div>
  {/if}

  <!-- combat stats -->
  {#if statRows.length > 0}
    <div class="px-3 py-2 border-t border-line/20">
      <div class="grid grid-cols-2 gap-x-3 gap-y-1">
        {#each statRows as row (row.label)}
          <div class="flex items-center gap-1.5 text-[11px]">
            <Icon icon={row.icon} width={11} class="text-accent shrink-0" />
            <span class="text-ink-muted">{row.label}</span>
            <span class="text-ink-primary font-semibold tabular-nums ml-auto">{row.value}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- durability bar (weapons/armor only) -->
  {#if (isWeapon || isArmor) && dyn?.durability != null && meta?.durability}
    <div class="px-3 py-2 border-t border-line/20 space-y-1">
      <div class="flex justify-between text-[10px]">
        <span class="text-ink-muted flex items-center gap-1">
          <Icon icon="lucide:shield-check" width={10} />
          Durability
        </span>
        <span class="text-ink-secondary tabular-nums">{Math.round(dyn.durability)} / {meta.durability}</span>
      </div>
      {#if durPct !== null}
        <div class="h-1.5 rounded-full bg-bg-deep overflow-hidden">
          <div class="h-full {durColor} transition-all" style="width: {durPct}%"></div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- remaining bullets (weapons only) -->
  {#if dyn?.type === 'weapon' && dyn.remaining_bullets != null && dyn.remaining_bullets > 0}
    <div class="px-3 py-1.5 border-t border-line/20 flex items-center gap-1.5 text-[11px]">
      <Icon icon="lucide:circle-dot" width={11} class="text-ink-muted" />
      <span class="text-ink-muted">Loaded ammo:</span>
      <span class="text-ink-primary font-semibold tabular-nums">{dyn.remaining_bullets}</span>
    </div>
  {/if}

  <!-- weapon passive skills -->
  {#if dyn?.type === 'weapon' && dyn.passive_skills && dyn.passive_skills.length > 0}
    <div class="px-3 py-2 border-t border-line/20">
      <p class="text-[10px] text-ink-muted mb-1 flex items-center gap-1">
        <Icon icon="lucide:sparkles" width={10} />
        Passives ({dyn.passive_skills.length})
      </p>
      <div class="flex flex-wrap gap-1">
        {#each dyn.passive_skills as skill (skill)}
          <span class="px-1.5 py-px rounded-2 bg-accent/15 text-accent-light text-[10px] border border-accent/30">
            {skill.replace(/_/g, ' ')}
          </span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- egg pal info -->
  {#if dyn?.type === 'egg'}
    <div class="px-3 py-2 border-t border-line/20 space-y-1.5">
      {#if dyn.egg_gender || dyn.egg_talent_hp != null || dyn.egg_talent_shot != null || dyn.egg_talent_defense != null}
        <div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]">
          {#if dyn.egg_gender}
            <span class="flex items-center gap-1">
              <Icon icon={dyn.egg_gender === 'Female' ? 'lucide:venus' : 'lucide:mars'} width={11}
                class={dyn.egg_gender === 'Female' ? 'text-pink-400' : 'text-sky-400'} />
              <span class="text-ink-secondary">{dyn.egg_gender}</span>
            </span>
          {/if}
          {#if dyn.egg_talent_hp != null}
            <span class="text-ink-muted">HP <span class="text-ink-secondary tabular-nums">{dyn.egg_talent_hp}</span></span>
          {/if}
          {#if dyn.egg_talent_shot != null}
            <span class="text-ink-muted">ATK <span class="text-ink-secondary tabular-nums">{dyn.egg_talent_shot}</span></span>
          {/if}
          {#if dyn.egg_talent_defense != null}
            <span class="text-ink-muted">DEF <span class="text-ink-secondary tabular-nums">{dyn.egg_talent_defense}</span></span>
          {/if}
        </div>
      {/if}
      {#if dyn.egg_passive_skills && dyn.egg_passive_skills.length > 0}
        <div>
          <p class="text-[10px] text-ink-muted mb-1 flex items-center gap-1">
            <Icon icon="lucide:sparkles" width={10} />
            Egg Passives ({dyn.egg_passive_skills.length})
          </p>
          <div class="flex flex-wrap gap-1">
            {#each dyn.egg_passive_skills as skill (skill)}
              <span class="px-1.5 py-px rounded-2 bg-emerald-500/15 text-emerald-300 text-[10px] border border-emerald-500/30">
                {skill.replace(/_/g, ' ')}
              </span>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- footer: weight + item id -->
  <div class="px-3 py-1.5 border-t border-line/20 flex items-center justify-between text-[10px]">
    {#if totalWeight}
      <span class="flex items-center gap-1 text-ink-muted">
        <Icon icon="lucide:weight" width={10} />
        <span class="tabular-nums">{totalWeight}</span>
      </span>
    {:else}
      <span></span>
    {/if}
    <code class="font-mono text-ink-dim truncate ml-2">{item.static_id}</code>
  </div>
</div>
