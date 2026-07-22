<script lang="ts">
  /**
   * BreedingSidePanel — right-hand panel for Graph Mode.
   *
   * Contains: chain selector tabs, configuration inputs (target, gender,
   * generations, max results), selection-pool or save-owner controls, the
   * compute button, and a node-detail section that appears when a graph node
   * is clicked.
   *
   * The parent page owns all state; we accept it via props and emit changes
   * via callback props.
   */
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import type {
    BreedablePal,
    Chain,
    PlayerSummary,
  } from '$types/index';
  import PalPicker from './PalPicker.svelte';
  import PalSlot from './PalSlot.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';

  // ── Node detail (from graph click) ──
  interface NodeDetail {
    id: string;
    tribe: string;
    display: string;
    icon: string | null;
    gender?: string | null;
    passives: string[];
    sourceType?: string;
    isBred: boolean;
    isTarget?: boolean;
    stepIndex?: number;
  }

  interface Props {
    /** When true, the panel collapses to a thin bar (maximizes graph space). */
    collapsed?: boolean;
    oncollapsedChange?: (val: boolean) => void;

    // Mode
    mode: 'direct' | 'selection' | 'save';

    // ── Direct mode props ──
    directSub?: string;
    ondirectSubChange?: (sub: string) => void;
    parentA?: string | null;
    onparentAChange?: (t: string) => void;
    parentB?: string | null;
    onparentBChange?: (t: string) => void;
    directTarget?: string | null;
    ondirectTargetChange?: (t: string) => void;
    canRunDirect?: boolean;
    directLoading?: boolean;
    oncomputeDirect?: () => void;

    // Chains (selection/save mode)
    chains: Chain[];
    activeChainIndex: number;
    onactiveChainIndexChange?: (idx: number) => void;

    // Chain config
    chainTarget: string | null;
    onchainTargetChange?: (t: string) => void;
    chainGender: string | null;
    onchainGenderChange?: (g: string | null) => void;
    chainGens: number;
    onchainGensChange?: (n: number) => void;
    chainMaxResults: number;
    onchainMaxResultsChange?: (n: number) => void;

    // Selection mode
    selectedPool: { tribe: string; gender: string | null }[];
    onaddToPool?: (tribe: string) => void;
    onremoveFromPool?: (tribe: string) => void;
    onsetPoolGender?: (tribe: string, gender: string | null) => void;

    // Save mode
    players: PlayerSummary[];
    ownerUid: string | null;
    onownerUidChange?: (uid: string | null) => void;
    includeWild: boolean;
    onincludeWildChange?: (val: boolean) => void;
    saveLoaded: boolean;

    // Compute (chain mode)
    computing: boolean;
    canRunChain: boolean;
    oncompute?: () => void;
    error: string | null;

    // Pal map (for display)
    palMap: Map<string, BreedablePal>;
    passiveName?: (asset: string) => string;

    // Selected node detail (from graph click)
    selectedNode: NodeDetail | null;
  }

  let {
    collapsed = false,
    oncollapsedChange,
    mode,
    // Direct mode
    directSub = 'forward',
    ondirectSubChange,
    parentA = null,
    onparentAChange,
    parentB = null,
    onparentBChange,
    directTarget = null,
    ondirectTargetChange,
    canRunDirect = false,
    directLoading = false,
    oncomputeDirect,
    // Chains
    chains,
    activeChainIndex,
    onactiveChainIndexChange,
    chainTarget,
    onchainTargetChange,
    chainGender,
    onchainGenderChange,
    chainGens,
    onchainGensChange,
    chainMaxResults,
    onchainMaxResultsChange,
    selectedPool,
    onaddToPool,
    onremoveFromPool,
    onsetPoolGender,
    players,
    ownerUid,
    onownerUidChange,
    includeWild,
    onincludeWildChange,
    saveLoaded,
    computing,
    canRunChain,
    oncompute,
    error,
    palMap,
    passiveName = (asset: string) => asset,
    selectedNode,
  }: Props = $props();

  // ── Save-mode owner search state ──
  let ownerSearch = $state('');
  let ownerFocus = $state(false);
  let ownerBlurTimer: ReturnType<typeof setTimeout> | undefined;

  const filteredPlayers = $derived(
    ownerSearch
      ? players.filter((pl) => {
          const q = ownerSearch.toLowerCase();
          return (
            pl.name.toLowerCase().includes(q) ||
            pl.uid.toLowerCase().includes(q) ||
            (pl.guild_name ?? '').toLowerCase().includes(q)
          );
        })
      : players,
  );
</script>

<div class="flex flex-col h-full overflow-y-auto">
  <!-- Collapse/expand toggle (top-right of the panel) -->
  <div class="flex items-center justify-between px-3 py-1.5 border-b border-line/20 shrink-0">
    <span class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider {collapsed ? 'hidden' : ''}">
      Controls
    </span>
    <button
      class="btn btn-secondary p-1 rounded-3 text-ink-dim hover:text-ink-primary transition-fast"
      onclick={() => oncollapsedChange?.(!collapsed)}
      title={collapsed ? 'Expand panel' : 'Collapse panel'}
    >
      {#if collapsed}
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      {:else}
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      {/if}
    </button>
  </div>

  {#if collapsed}
    <!-- When collapsed: show only a spacer/minimal content -->
    <div class="flex flex-col items-center gap-2 py-3 text-ink-dim">
      <span class="text-[9px] font-medium">Cfg</span>
    </div>
  {:else}
    <!-- ── Chain selector ── -->
    {#if chains.length > 0}
      <div class="px-3 pt-3 pb-2 border-b border-line/20">
        <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-1.5">
          {$t('web.breeding.chains')} ({chains.length})
        </span>
        <div class="flex flex-wrap gap-1">
          {#each chains as chain, i}
            <button
              class="px-2 py-1 rounded-3 text-[10px] font-medium transition-all {i === activeChainIndex
                ? 'bg-accent/15 text-accent border border-accent/40'
                : 'text-ink-secondary hover:bg-bg-hover border border-line/30'}"
              onclick={() => onactiveChainIndexChange?.(i)}
              title="{palMap.get(chain.target)?.display_name ?? chain.target} — {chain.generations} gen"
            >
              {i + 1}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#if mode === 'direct'}
      <!-- ── DIRECT MODE configuration ── -->
      <div class="px-3 py-3 border-b border-line/20 space-y-2.5">
        <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider">Direct</span>

        <!-- Sub-mode selector -->
        <div class="flex gap-1">
          {#each ['forward', 'reverse', 'parents'] as sub}
            <button
              class="px-2 py-1 rounded-3 text-[9px] font-medium transition-all {directSub === sub
                ? 'bg-bg-hover text-ink-primary border border-line/60'
                : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
              onclick={() => ondirectSubChange?.(sub)}
            >{sub === 'forward' ? 'A+B→C' : sub === 'reverse' ? 'A+T→B' : 'T→P'}</button>
          {/each}
        </div>

        {#if directSub !== 'parents'}
          <div>
            <span class="block text-[10px] text-ink-dim mb-0.5">Parent A</span>
            <PalPicker value={parentA} onselect={(t) => onparentAChange?.(t)} />
          </div>
        {/if}
        {#if directSub === 'forward'}
          <div>
            <span class="block text-[10px] text-ink-dim mb-0.5">Parent B</span>
            <PalPicker value={parentB} onselect={(t) => onparentBChange?.(t)} exclude={parentA ? [parentA] : []} />
          </div>
        {:else if directSub === 'reverse' || directSub === 'parents'}
          <div>
            <span class="block text-[10px] text-ink-dim mb-0.5">Target</span>
            <PalPicker value={directTarget} onselect={(t) => ondirectTargetChange?.(t)} />
          </div>
        {/if}

        <button class="btn btn-primary text-xs w-full flex items-center justify-center gap-1.5"
          disabled={!canRunDirect || directLoading} onclick={oncomputeDirect}>
          {#if directLoading}<Spinner size={14} />{:else}<Icon icon="lucide:play" width={13} />{/if}
          Compute
        </button>
        {#if error}<p class="text-[10px] text-rose-400">{error}</p>{/if}
      </div>

    {:else}
      <!-- ── CHAIN MODE configuration ── -->
      <div class="px-3 py-3 border-b border-line/20 space-y-2.5">
        <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider">
          {$t('web.breeding.configuration')}
        </span>
        <div>
          <span class="block text-[10px] text-ink-dim mb-0.5">{$t('web.breeding.target')}</span>
          <PalPicker value={chainTarget} onselect={(t) => onchainTargetChange?.(t)} />
        </div>
        <div>
          <span class="block text-[10px] text-ink-dim mb-0.5">{$t('web.breeding.gender')}</span>
          <select class="input text-xs w-full" value={chainGender ?? ''}
            onchange={(e) => onchainGenderChange?.((e.currentTarget as HTMLSelectElement).value || null)}>
            <option value="">{$t('web.breeding.any_gender')}</option>
            <option value="Male">{$t('web.breeding.male')}</option>
            <option value="Female">{$t('web.breeding.female')}</option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <span class="block text-[10px] text-ink-dim mb-0.5">{$t('web.breeding.max_generations')}</span>
            <input type="number" min="1" max="6" class="input text-xs w-full" value={chainGens}
              oninput={(e) => onchainGensChange?.(parseInt((e.currentTarget as HTMLInputElement).value) || 4)} />
          </div>
          <div>
            <span class="block text-[10px] text-ink-dim mb-0.5">{$t('web.breeding.max_results')}</span>
            <input type="number" min="1" max="10" class="input text-xs w-full" value={chainMaxResults}
              oninput={(e) => onchainMaxResultsChange?.(parseInt((e.currentTarget as HTMLInputElement).value) || 5)} />
          </div>
        </div>
      </div>

      <!-- ── Selection / Save pool section ── -->
      <div class="px-3 py-3 border-b border-line/20 space-y-2.5">
        {#if mode === 'selection'}
          <div>
            <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-1.5">
              {$t('web.breeding.pool')} ({selectedPool.length})
            </span>
            <PalPicker placeholder={$t('web.breeding.add_to_pool')} onselect={(t) => onaddToPool?.(t)}
              exclude={selectedPool.map((p) => p.tribe)} />
            {#if selectedPool.length}
              <div class="flex flex-wrap gap-1 mt-1.5">
                {#each selectedPool as member}
                  <div class="flex items-center gap-1 px-1.5 py-0.5 rounded-4 bg-bg-deep/50 border border-line/30">
                    <PalSlot tribe={member.tribe} display={palMap.get(member.tribe)?.display_name}
                      icon={palMap.get(member.tribe)?.icon} size="sm" />
                    <select class="bg-transparent text-[8px] text-ink-dim outline-none cursor-pointer"
                      value={member.gender ?? ''}
                      onchange={(e) => onsetPoolGender?.(member.tribe, (e.currentTarget as HTMLSelectElement).value || null)}>
                      <option value="">Any</option><option value="Male">M</option><option value="Female">F</option>
                    </select>
                    <button class="text-ink-dim hover:text-rose-400 transition-fast"
                      onclick={() => onremoveFromPool?.(member.tribe)} title="Remove">
                      <Icon icon="lucide:x" width={10} />
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          {#if !saveLoaded}
            <div class="text-xs text-ink-dim italic py-2 text-center">{$t('web.breeding.save_required_hint')}</div>
          {:else}
            <div class="space-y-2.5">
              <div>
                <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-1">{$t('web.breeding.owner')}</span>
                <div class="relative">
                  <input type="text" class="input text-xs w-full"
                    value={ownerUid ? players.find((p) => p.uid === ownerUid)?.name ?? ownerUid : ownerSearch}
                    placeholder={$t('web.breeding.owner_search')}
                    oninput={(e) => { ownerSearch = (e.currentTarget as HTMLInputElement).value; if (ownerUid) onownerUidChange?.(null); }}
                    onfocus={() => { if (ownerBlurTimer) clearTimeout(ownerBlurTimer); ownerFocus = true; }}
                    onblur={() => { ownerBlurTimer = setTimeout(() => { ownerFocus = false; }, 200); }} />
                  {#if ownerFocus}
                    <div class="absolute left-0 right-0 z-20 mt-1 max-h-40 overflow-y-auto rounded-6 border border-line/40 bg-bg-deep shadow-card-lg" role="listbox">
                      <button class="w-full text-left px-2.5 py-1.5 text-[10px] text-ink-muted hover:bg-bg-hover transition-fast border-b border-line/20 last:border-b-0 {ownerUid === null ? 'bg-accent/10' : ''}"
                        onmousedown={() => { onownerUidChange?.(null); ownerSearch = ''; ownerFocus = false; }}>{$t('web.breeding.all_players')}</button>
                      {#each filteredPlayers as pl}
                        <button class="w-full text-left px-2.5 py-1.5 text-[10px] text-ink-primary hover:bg-bg-hover transition-fast border-b border-line/20 last:border-b-0 {ownerUid === pl.uid ? 'bg-accent/10' : ''}"
                          onmousedown={() => { onownerUidChange?.(pl.uid); ownerSearch = ''; ownerFocus = false; }}>
                          {pl.name}<span class="text-ink-dim ml-1">({pl.pal_count})</span>
                        </button>
                      {/each}
                      {#if filteredPlayers.length === 0 && ownerSearch}
                        <div class="px-2.5 py-1.5 text-[10px] text-ink-dim">{$t('web.breeding.owner_no_match')}</div>
                      {/if}
                    </div>
                  {/if}
                </div>
              </div>
              <label class="flex items-center gap-1.5 text-[10px] text-ink-secondary cursor-pointer">
                <input type="checkbox" checked={includeWild} onchange={(e) => onincludeWildChange?.((e.currentTarget as HTMLInputElement).checked)} class="accent-accent" />
                {$t('web.breeding.include_wild')}
              </label>
            </div>
          {/if}
        {/if}
      </div>

      <!-- ── Compute button + error (chain mode) ── -->
      <div class="px-3 py-3 border-b border-line/20 space-y-1.5">
        <button class="btn btn-primary text-xs w-full flex items-center justify-center gap-1.5"
          disabled={!canRunChain || computing} onclick={oncompute}>
          {#if computing}<Spinner size={14} />{:else}<Icon icon="lucide:route" width={13} />{/if}
          {$t('web.breeding.find_chains')}
        </button>
        {#if error}<p class="text-[10px] text-rose-400">{error}</p>{/if}
      </div>
    {/if}

    <!-- ── Node detail section ── -->
    {#if selectedNode}
      <div class="px-3 py-3 border-b border-line/20 space-y-2">
        <span class="block text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.breeding.node_details')}</span>
        <div class="flex items-start gap-2.5">
          <img src={assetUrl(selectedNode.icon)} alt={selectedNode.display}
            class="w-10 h-10 rounded-4 object-cover border border-line/40 shrink-0" onerror={imgOnError} />
          <div class="min-w-0 space-y-0.5">
            <div class="flex items-center gap-1.5">
              <span class="font-semibold text-xs text-ink-emphasis truncate">{selectedNode.display}</span>
              {#if selectedNode.gender === 'Male'}<Icon icon="lucide:mars" width={10} class="text-accent-light shrink-0" />
              {:else if selectedNode.gender === 'Female'}<Icon icon="lucide:venus" width={10} class="text-pink-300 shrink-0" />{/if}
            </div>
            <div class="text-[9px] text-ink-dim font-mono">{selectedNode.tribe}</div>
            {#if selectedNode.isTarget}<div class="text-[9px] text-accent font-semibold">Target</div>
            {:else if selectedNode.isBred && selectedNode.stepIndex !== undefined}<div class="text-[9px] text-accent-cyan">Step {selectedNode.stepIndex + 1} · Bred</div>
            {:else if selectedNode.sourceType === 'owned'}<div class="text-[9px] text-accent">Owned</div>
            {:else if selectedNode.sourceType === 'selected'}<div class="text-[9px] text-emerald-400">Selected</div>
            {:else if selectedNode.sourceType === 'wild'}<div class="text-[9px] text-amber-400">Wild</div>{/if}
          </div>
        </div>
        {#if selectedNode.passives.length}
          <div class="flex flex-wrap gap-1">
            {#each selectedNode.passives as p}
              <span class="chip text-[8px] px-1.5 py-0 {chains[activeChainIndex]?.matched_passives.includes(p) ? 'chip-green' : ''}">{passiveName(p)}</span>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
