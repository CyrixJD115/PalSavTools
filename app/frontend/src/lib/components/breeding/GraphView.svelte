<script lang="ts">
  /**
   * GraphView — wraps the dendrogram for the currently-active item.
   *
   * Supports both chain mode (breeding chains with steps) and Direct mode
   * (simple parent A + parent B → child trees). Accepts pre-built TreeNode
   * arrays via the `trees` prop.
   *
   * Features:
   * - Prev/next navigation when multiple trees
   * - Per-gen / All-in-one layout toggle (chain mode only)
   * - Generation depth slider (per-gen mode)
   * - Chain header with target/gen count/gender feasibility/passives
   */
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import type { BreedablePal } from '$types/index';
  import type { Chain } from '$types/index';
  import type { TreeNode } from '$lib/breeding/dendrogram/types';
  import ChainDendrogram from './ChainDendrogram.svelte';

  interface Props {
    /** Pre-built tree nodes to display. */
    trees: TreeNode[];
    /** Original chains (needed for header metadata in chain mode). */
    chains?: Chain[];
    palMap: Map<string, BreedablePal>;
    passiveName?: (asset: string) => string;
    /** Index of the active tree within `trees`. */
    activeIndex: number;
    onactiveIndexChange?: (idx: number) => void;

    // Layout mode
    graphLayout: 'all-in-one' | 'per-gen';
    ongraphLayoutChange?: (val: 'all-in-one' | 'per-gen') => void;
    /** Current generation depth for per-gen mode (1-based). */
    currentGen?: number;
    oncurrentGenChange?: (val: number) => void;
    /** Maximum generation depth (from the chain). */
    maxDepth?: number;

    // Selection callback (node click)
    onselect?: (node: TreeNode | null) => void;
  }

  let {
    trees,
    chains = [],
    palMap,
    passiveName = (asset: string) => asset,
    activeIndex = 0,
    onactiveIndexChange,
    graphLayout = 'all-in-one',
    ongraphLayoutChange,
    currentGen = 1,
    oncurrentGenChange,
    maxDepth = 1,
    onselect,
  }: Props = $props();

  const activeTree = $derived(trees[activeIndex]);
  const totalTrees = $derived(trees.length);

  // For chain mode: resolve the active chain for header metadata.
  const activeChain = $derived(chains[activeIndex]);

  function prev() {
    if (activeIndex > 0) onactiveIndexChange?.(activeIndex - 1);
  }
  function next() {
    if (activeIndex < totalTrees - 1) onactiveIndexChange?.(activeIndex + 1);
  }
</script>

<div class="flex flex-col h-full min-h-0">
  <!-- Toolbar row: navigation + layout toggles -->
  <div class="flex items-center justify-between gap-2 px-3 py-1.5 shrink-0 border-b border-line/30">
    <!-- Left: nav + chain info -->
    <div class="flex items-center gap-2 min-w-0">
      {#if totalTrees > 0}
        <div class="flex items-center gap-0.5 mr-1">
          <button
            class="btn btn-secondary p-1 rounded-3 text-ink-dim hover:text-ink-primary disabled:opacity-30 disabled:cursor-not-allowed transition-fast"
            onclick={prev}
            disabled={activeIndex <= 0}
            title="Previous"
          >
            <Icon icon="lucide:chevron-left" width={12} />
          </button>
          <span class="text-[10px] text-ink-dim font-mono px-1 tabular-nums shrink-0">
            {totalTrees > 0 ? `${activeIndex + 1}/${totalTrees}` : '0/0'}
          </span>
          <button
            class="btn btn-secondary p-1 rounded-3 text-ink-dim hover:text-ink-primary disabled:opacity-30 disabled:cursor-not-allowed transition-fast"
            onclick={next}
            disabled={activeIndex >= totalTrees - 1}
            title="Next"
          >
            <Icon icon="lucide:chevron-right" width={12} />
          </button>
        </div>
      {/if}

      {#if activeChain}
        <Icon icon="lucide:git-merge" width={14} class="text-accent shrink-0" />
        <h3 class="text-sm font-semibold text-ink-emphasis truncate">
          {palMap.get(activeChain.target)?.display_name ?? activeChain.target}
        </h3>
        <span class="chip text-[9px] px-1.5 py-0.5 chip-blue shrink-0">{activeChain.generations} gen</span>
        {#if activeChain.gender_feasible}
          <Icon icon="lucide:check-circle-2" width={11} class="text-emerald-400 shrink-0" />
        {:else}
          <Icon icon="lucide:x-circle" width={11} class="text-rose-400 shrink-0" />
        {/if}
        {#if activeChain.matched_passives.length}
          <div class="flex flex-wrap gap-1 shrink-0 ml-1">
            {#each activeChain.matched_passives as passive}
              <span class="chip chip-green text-[8px] px-1.5 py-0">{passiveName(passive)}</span>
            {/each}
          </div>
        {/if}
      {:else if activeTree}
        <Icon icon="lucide:arrow-right-left" width={14} class="text-accent shrink-0" />
        <h3 class="text-sm font-semibold text-ink-emphasis truncate">
          {activeTree.display}
        </h3>
      {/if}
    </div>

    <!-- Right: per-gen / all-in-one toggle (chain mode only) -->
    {#if chains.length > 0 && maxDepth !== undefined && maxDepth > 1}
      <div class="flex items-center gap-1.5 shrink-0">
        <!-- Per-gen / All-in-one toggle -->
        <div class="flex gap-0.5 p-0.5 rounded-3 bg-bg-deep/50 border border-line/30">
          <button
            class="px-1.5 py-0.5 rounded-2 text-[9px] font-medium transition-all {graphLayout === 'all-in-one'
              ? 'bg-accent/15 text-accent border border-accent/40'
              : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
            onclick={() => ongraphLayoutChange?.('all-in-one')}
            title="Show all generations"
          >
            All
          </button>
          <button
            class="px-1.5 py-0.5 rounded-2 text-[9px] font-medium transition-all {graphLayout === 'per-gen'
              ? 'bg-accent/15 text-accent border border-accent/40'
              : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
            onclick={() => ongraphLayoutChange?.('per-gen')}
            title="Show one generation at a time"
          >
            Per-Gen
          </button>
        </div>

        {#if graphLayout === 'per-gen'}
          <!-- Generation slider -->
          <div class="flex items-center gap-1">
            <span class="text-[9px] text-ink-dim whitespace-nowrap">Gen</span>
            <input
              type="range"
              min="1"
              max={maxDepth}
              class="w-16 h-1 accent-accent cursor-pointer"
              value={currentGen}
              oninput={(e) => oncurrentGenChange?.(parseInt((e.currentTarget as HTMLInputElement).value) || 1)}
            />
            <span class="text-[10px] text-ink-primary font-mono w-4 text-right tabular-nums">{currentGen}</span>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Dendrogram -->
  {#if activeTree}
    <div class="flex-1 min-h-0">
      <ChainDendrogram
        treeNode={activeTree}
        {palMap}
        {passiveName}
        fullHeight={true}
        {onselect}
      />
    </div>
  {:else}
    <div class="flex-1 flex items-center justify-center text-xs text-ink-dim italic">
      No tree to display
    </div>
  {/if}
</div>
