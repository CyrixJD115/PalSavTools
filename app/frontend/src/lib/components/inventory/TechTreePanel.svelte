<script lang="ts">
  // Tech Tree panel — the reusable content of the Tech Tree editor. Renders
  // inline (in the Inventory page's Tech Tree tab) or wrapped by TechTreeModal
  // for the popup variant. Owns the editable unlock set + Apply logic.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import { loadTechnologies, techIconUrl } from '$lib/utils/technologies';
  import { imgOnError } from '$lib/utils/assetUrl';
  import type { Technology, PlayerTechnologiesResponse } from '$types/index';

  let { uid }: { uid: string } = $props();

  let allTechs = $state<Technology[]>([]);
  let current = $state<Set<string>>(new Set());
  let edited = $state<Set<string>>(new Set());
  let meta = $state<PlayerTechnologiesResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saving = $state(false);

  let search = $state('');
  let filter = $state<'all' | 'standard' | 'boss'>('all');
  let showOnlyLocked = $state(false);

  onMount(() => { void load(); });

  async function load() {
    loading = true; error = null;
    try {
      const [techs, playerTech] = await Promise.all([
        loadTechnologies(),
        api.playerTechnologies(uid),
      ]);
      allTechs = techs;
      meta = playerTech;
      current = new Set(playerTech.technologies);
      edited = new Set(playerTech.technologies);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  const grouped = $derived.by(() => {
    const map = new Map<number, { standard: Technology[]; boss: Technology[] }>();
    for (const tech of allTechs) {
      const lvl = tech.level_cap;
      if (!map.has(lvl)) map.set(lvl, { standard: [], boss: [] });
      const bucket = map.get(lvl)!;
      if (tech.is_boss_tech) bucket.boss.push(tech);
      else bucket.standard.push(tech);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  });

  const filteredGroups = $derived.by(() => {
    const q = search.trim().toLowerCase();
    return grouped
      .map(([lvl, buckets]) => {
        const filterFn = (tech: Technology) => {
          if (filter === 'standard' && tech.is_boss_tech) return false;
          if (filter === 'boss' && !tech.is_boss_tech) return false;
          if (showOnlyLocked && edited.has(tech.asset)) return false;
          if (!q) return true;
          return tech.name.toLowerCase().includes(q) || tech.asset.toLowerCase().includes(q);
        };
        return [lvl, { standard: buckets.standard.filter(filterFn), boss: buckets.boss.filter(filterFn) }] as const;
      })
      .filter(([, buckets]) => buckets.standard.length > 0 || buckets.boss.length > 0);
  });

  const editedCount = $derived(edited.size);
  const dirty = $derived(edited.size !== current.size || [...edited].some((a) => !current.has(a)));
  const changesCount = $derived.by(() => {
    let n = 0;
    for (const a of edited) if (!current.has(a)) n++;
    for (const a of current) if (!edited.has(a)) n++;
    return n;
  });

  function toggle(asset: string) {
    const next = new Set(edited);
    if (next.has(asset)) next.delete(asset);
    else next.add(asset);
    edited = next;
  }

  function unlockAll() {
    if (!confirm($t('web.inventory.tech_unlock_all_confirm', 'Unlock all 588 technologies?'))) return;
    edited = new Set(allTechs.map((t) => t.asset));
  }

  function lockAll() {
    if (!confirm($t('web.inventory.tech_lock_all_confirm', 'Lock ALL technologies? This removes every recipe.'))) return;
    edited = new Set();
  }

  async function apply() {
    saving = true; error = null;
    try {
      await api.setPlayerTechnologies(uid, { technologies: [...edited] });
      current = new Set(edited);
      toast.success($t('web.inventory.tech_applied', 'Tech tree updated.'));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  const FILTER_TABS = [
    { key: 'all' as const,      label: $t('web.inventory.tech_filter_all', 'All'),      icon: 'lucide:layers' },
    { key: 'standard' as const, label: $t('web.inventory.tech_filter_standard', 'Standard'), icon: 'lucide:book-open' },
    { key: 'boss' as const,     label: $t('web.inventory.tech_filter_ancient', 'Ancient'), icon: 'lucide:atom' },
  ];
</script>

<div class="flex flex-col h-full">
  {#if loading}
    <div class="flex-1 flex justify-center items-center py-16"><Spinner size={24} /></div>
  {:else if error}
    <p class="text-sm text-status-error p-4">{error}</p>
  {:else}
    <!-- toolbar -->
    <div class="flex items-center gap-2.5 p-3 border-b border-line/20 flex-wrap shrink-0 bg-bg-surface/50">
      {#if meta}
        <Badge tone="accent" class="!text-[11px] !px-2.5 !py-1">
          <Icon icon="lucide:flask-conical" width={12} class="mr-1" />
          {meta.tech_points}
        </Badge>
        <Badge tone="amber" class="!text-[11px] !px-2.5 !py-1">
          <Icon icon="lucide:atom" width={12} class="mr-1" />
          {meta.boss_tech_points}
        </Badge>
        <span class="text-[11px] text-ink-muted">
          <span class="font-semibold text-ink-secondary">{editedCount}</span>/{allTechs.length}
          <span class="hidden sm:inline"> {$t('web.inventory.tech_unlocked', 'unlocked')}</span>
        </span>
      {/if}

      <div class="flex-1 min-w-0"></div>

      <div class="relative">
        <Icon icon="lucide:search" width={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
        <input
          type="text"
          class="input text-sm pl-8 w-44"
          placeholder={$t('web.inventory.tech_search_placeholder', 'Search recipes…')}
          bind:value={search}
        />
      </div>

      <div class="flex gap-px rounded-6 overflow-hidden border border-line/40">
        {#each FILTER_TABS as ft (ft.key)}
          <button
            type="button"
            class="px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-all
              {filter === ft.key ? 'bg-accent/15 text-accent-light' : 'bg-bg-deep text-ink-secondary hover:bg-bg-hover'}"
            onclick={() => (filter = ft.key)}
          >
            <Icon icon={ft.icon} width={13} />
            {ft.label}
          </button>
        {/each}
      </div>

      <label class="flex items-center gap-1.5 text-xs text-ink-muted cursor-pointer select-none hover:text-ink-secondary transition-fast">
        <input type="checkbox" bind:checked={showOnlyLocked} class="accent-accent w-3.5 h-3.5" />
        {$t('web.inventory.tech_only_locked', 'Locked only')}
      </label>
    </div>

    <!-- tech grid (scrollable) -->
    <div class="flex-1 overflow-y-auto p-4 space-y-1 min-h-0">
      {#each filteredGroups as [lvl, buckets] (lvl)}
        {@const rowEven = lvl % 2 === 0}
        <div class="flex items-start gap-3 py-2 px-2 rounded-4 {rowEven ? 'bg-bg-deep/30' : ''}">
          <!-- level badge -->
          <div class="w-10 shrink-0 pt-1 flex flex-col items-center">
            <span class="text-[13px] font-bold text-accent tabular-nums leading-none">{lvl}</span>
            <span class="text-[7px] text-ink-dim uppercase tracking-wider mt-0.5">Lv</span>
          </div>

          <!-- standard techs -->
          <div class="flex flex-wrap gap-1.5 flex-1 min-w-0">
            {#each buckets.standard as tech (tech.asset)}
              {@const unlocked = edited.has(tech.asset)}
              <div class="relative group/tile">
                <button
                  type="button"
                  class="flex flex-col items-center w-16 p-0.5 pt-1 rounded-4 border transition-all duration-100
                    {unlocked
                      ? 'bg-accent/10 border-accent/35'
                      : 'bg-bg-deep/60 border-line/30 hover:border-line/60 opacity-65 hover:opacity-85'}"
                  onclick={() => toggle(tech.asset)}
                  aria-pressed={unlocked}
                >
                  <div class="relative w-9 h-9 flex items-center justify-center">
                    <img
                      src={techIconUrl(tech.icon)}
                      alt={tech.name}
                      class="w-8 h-8 object-contain {unlocked ? '' : 'grayscale opacity-60'}"
                      onerror={imgOnError}
                      loading="lazy"
                    />
                    {#if unlocked}
                      <span class="absolute -top-1 -left-1 w-3.5 h-3.5 rounded-full bg-accent border border-bg-surface flex items-center justify-center shadow-sm">
                        <Icon icon="lucide:check" width={9} class="text-white" />
                      </span>
                    {:else}
                      <span class="absolute -top-1 -left-1 w-3.5 h-3.5 rounded-full bg-bg-elevated border border-line/60 flex items-center justify-center">
                        <Icon icon="lucide:lock" width={8} class="text-ink-dim" />
                      </span>
                    {/if}
                  </div>
                  <span class="text-[9px] text-ink-muted tabular-nums font-medium leading-tight mt-0.5">{tech.cost}</span>
                  <span class="text-[7px] text-ink-dim leading-tight line-clamp-1 w-full text-center px-0.5">{tech.name}</span>
                </button>

                <!-- hover tooltip (right side, avoids scroll-container clipping) -->
                <div class="absolute z-50 left-full top-0 ml-2 hidden group-hover/tile:block pointer-events-none">
                  <div class="w-64 bg-bg-surface border border-line/40 rounded-6 shadow-xl p-2.5 text-xs space-y-1.5">
                    <div class="flex items-start gap-2">
                      <img
                        src={techIconUrl(tech.icon)}
                        alt={tech.name}
                        class="w-9 h-9 object-contain shrink-0 rounded-2 bg-bg-deep/60 border border-line/30 p-0.5"
                        onerror={imgOnError}
                      />
                      <div class="min-w-0">
                        <p class="font-semibold text-ink-primary text-sm leading-tight">{tech.name}</p>
                        <p class="text-[9px] text-ink-dim tabular-nums">{tech.cost} pts · Lv.{tech.level_cap}</p>
                      </div>
                    </div>
                    {#if tech.description}
                      <p class="text-ink-muted text-[11px] leading-snug whitespace-pre-line">{tech.description}</p>
                    {/if}
                    <div class="flex flex-wrap gap-1.5 pt-1 border-t border-line/20">
                      {#if tech.require_tower_boss !== 'None'}
                        <span class="text-[10px] flex items-center gap-1 text-amber-300">
                          <Icon icon="lucide:skull" width={10} />
                          {tech.require_tower_boss}
                        </span>
                      {/if}
                      {#if tech.require_technology}
                        <span class="text-[10px] text-ink-muted">Prereq: {tech.require_technology}</span>
                      {/if}
                    </div>
                    {#if tech.unlock_item_recipes.length > 0 || tech.unlock_build_objects.length > 0}
                      <div class="pt-1 border-t border-line/20">
                        {#if tech.unlock_item_recipes.length > 0}
                          <p class="text-[9px] text-ink-dim uppercase tracking-wider mb-0.5">Unlocks items:</p>
                          <div class="flex flex-wrap gap-0.5">
                            {#each tech.unlock_item_recipes.slice(0, 6) as item}
                              <span class="px-1 py-px rounded-2 bg-accent/10 text-accent-light text-[9px] border border-accent/20">{item}</span>
                            {/each}
                            {#if tech.unlock_item_recipes.length > 6}
                              <span class="text-[9px] text-ink-dim">+{tech.unlock_item_recipes.length - 6}</span>
                            {/if}
                          </div>
                        {/if}
                        {#if tech.unlock_build_objects.length > 0}
                          <p class="text-[9px] text-ink-dim uppercase tracking-wider mt-1 mb-0.5">Unlocks buildings:</p>
                          <div class="flex flex-wrap gap-0.5">
                            {#each tech.unlock_build_objects.slice(0, 4) as obj}
                              <span class="px-1 py-px rounded-2 bg-emerald-500/10 text-emerald-300 text-[9px] border border-emerald-500/20">{obj}</span>
                            {/each}
                            {#if tech.unlock_build_objects.length > 4}
                              <span class="text-[9px] text-ink-dim">+{tech.unlock_build_objects.length - 4}</span>
                            {/if}
                          </div>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>
          {#if buckets.boss.length > 0}
            <div class="shrink-0 w-20 border-l border-amber-500/20 pl-2.5 flex flex-col gap-1.5">
              {#each buckets.boss as tech (tech.asset)}
                {@const unlocked = edited.has(tech.asset)}
                <div class="relative group/tile">
                  <button
                    type="button"
                    class="flex flex-col items-center w-16 p-0.5 pt-1 rounded-4 border transition-all duration-100
                      {unlocked
                        ? 'bg-amber-500/8 border-amber-500/35'
                        : 'bg-bg-deep/60 border-line/30 hover:border-amber-500/30 opacity-65 hover:opacity-85'}"
                    onclick={() => toggle(tech.asset)}
                    aria-pressed={unlocked}
                  >
                    <div class="relative w-9 h-9 flex items-center justify-center">
                      <img
                        src={techIconUrl(tech.icon)}
                        alt={tech.name}
                        class="w-8 h-8 object-contain {unlocked ? '' : 'grayscale opacity-60'}"
                        onerror={imgOnError}
                        loading="lazy"
                      />
                      <span class="absolute -top-1 -left-1 px-0.5 py-px rounded-full bg-amber-500/30 border border-amber-500/60 text-[7px] text-amber-300 font-bold">A</span>
                      {#if unlocked}
                        <span class="absolute -top-1 -left-1 w-3.5 h-3.5 rounded-full bg-accent border border-bg-surface flex items-center justify-center shadow-sm">
                          <Icon icon="lucide:check" width={9} class="text-white" />
                        </span>
                      {/if}
                    </div>
                    <span class="text-[9px] text-amber-400/80 tabular-nums font-medium leading-tight mt-0.5">{tech.cost}</span>
                    <span class="text-[7px] text-ink-dim leading-tight line-clamp-1 w-full text-center px-0.5">{tech.name}</span>
                  </button>

                  <!-- hover tooltip (left side for ancient techs, avoids right-edge clipping) -->
                  <div class="absolute z-50 right-full top-0 mr-2 hidden group-hover/tile:block pointer-events-none">
                    <div class="w-64 bg-bg-surface border border-amber-500/30 rounded-6 shadow-xl p-2.5 text-xs space-y-1.5">
                      <div class="flex items-start gap-2">
                        <img
                          src={techIconUrl(tech.icon)}
                          alt={tech.name}
                          class="w-9 h-9 object-contain shrink-0 rounded-2 bg-bg-deep/60 border border-line/30 p-0.5"
                          onerror={imgOnError}
                        />
                        <div class="min-w-0">
                          <p class="font-semibold text-amber-300 text-sm leading-tight flex items-center gap-1.5">
                            <Icon icon="lucide:atom" width={14} class="text-amber-400 shrink-0" />
                            {tech.name}
                          </p>
                          <p class="text-[9px] text-ink-dim tabular-nums">{tech.cost} pts · Lv.{tech.level_cap}</p>
                        </div>
                      </div>
                      {#if tech.description}
                        <p class="text-ink-muted text-[11px] leading-snug whitespace-pre-line">{tech.description}</p>
                      {/if}
                      <div class="flex flex-wrap gap-1.5 pt-1 border-t border-line/20">
                        {#if tech.require_tower_boss !== 'None'}
                          <span class="text-[10px] flex items-center gap-1 text-amber-300">
                            <Icon icon="lucide:skull" width={10} />
                            {tech.require_tower_boss}
                          </span>
                        {/if}
                      </div>
                      {#if tech.unlock_item_recipes.length > 0 || tech.unlock_build_objects.length > 0}
                        <div class="pt-1 border-t border-line/20">
                          {#if tech.unlock_item_recipes.length > 0}
                            <p class="text-[9px] text-ink-dim uppercase tracking-wider mb-0.5">Unlocks items:</p>
                            <div class="flex flex-wrap gap-0.5">
                              {#each tech.unlock_item_recipes.slice(0, 6) as item}
                                <span class="px-1 py-px rounded-2 bg-amber-500/10 text-amber-300 text-[9px] border border-amber-500/20">{item}</span>
                              {/each}
                              {#if tech.unlock_item_recipes.length > 6}
                                <span class="text-[9px] text-ink-dim">+{tech.unlock_item_recipes.length - 6}</span>
                              {/if}
                            </div>
                          {/if}
                          {#if tech.unlock_build_objects.length > 0}
                            <p class="text-[9px] text-ink-dim uppercase tracking-wider mt-1 mb-0.5">Unlocks buildings:</p>
                            <div class="flex flex-wrap gap-0.5">
                              {#each tech.unlock_build_objects.slice(0, 4) as obj}
                                <span class="px-1 py-px rounded-2 bg-emerald-500/10 text-emerald-300 text-[9px] border border-emerald-500/20">{obj}</span>
                              {/each}
                              {#if tech.unlock_build_objects.length > 4}
                                <span class="text-[9px] text-ink-dim">+{tech.unlock_build_objects.length - 4}</span>
                              {/if}
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
        </div>
      {/if}
    </div>
    {/each}

      {#if filteredGroups.length === 0}
        <div class="text-center py-12 text-ink-dim text-sm">
          {$t('web.inventory.tech_no_results', 'No technologies match your filters.')}
        </div>
      {/if}
    </div>

    <!-- footer: bulk actions + apply -->
    <div class="flex items-center gap-2.5 p-3 border-t border-line/20 shrink-0 bg-bg-surface/50">
      <Button variant="secondary" onclick={unlockAll} disabled={saving} class="!text-sm">
        <Icon icon="lucide:unlock" width={14} class="mr-1.5" />
        {$t('web.inventory.tech_unlock_all', 'Unlock All')}
      </Button>
      <Button variant="ghost" onclick={lockAll} disabled={saving} class="!text-sm">
        <Icon icon="lucide:lock" width={14} class="mr-1.5" />
        {$t('web.inventory.tech_lock_all', 'Lock All')}
      </Button>

      <div class="flex-1"></div>

      {#if dirty}
        <span class="text-xs text-status-warning font-medium flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-status-warning"></span>
          {$t('web.inventory.tech_changes', { count: changesCount })}
        </span>
      {/if}

      <Button variant="ghost" onclick={() => (edited = new Set(current))} disabled={saving || !dirty} class="!text-sm">
        {$t('web.common.cancel')}
      </Button>
      <Button variant="primary" onclick={apply} disabled={saving || !dirty} class="!text-sm !px-4">
        {#if saving}<Icon icon="eos-icons:loading" width={15} class="mr-1.5" />{/if}
        {$t('web.inventory.tech_apply', 'Apply')}
      </Button>
    </div>
  {/if}
</div>
