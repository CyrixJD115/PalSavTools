<script lang="ts">
  // Breeding Calculator — three modes behind one page:
  //   • Direct   — A+B → child, and A+target → B options (PySide6 port)
  //   • Selection — chain to a target from a user-picked theoretical pool
  //   • Save     — chain to a target using ONLY the loaded save's owned pals
  //
  // Selection + Save share the same backend solver (/breeding/chain); the only
  // difference is the `mode` field and the source of the input pals. The pal
  // metadata (names/icons) is loaded once and shared across all pickers + result
  // rendering via the `palMap`.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import { api } from '$lib/api/client';
  import { saveLoaded } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
	import PalPicker from '$components/breeding/PalPicker.svelte';
	import PalSlot from '$components/breeding/PalSlot.svelte';
	import DirectResult from '$components/breeding/DirectResult.svelte';
	import ChainCard from '$components/breeding/ChainCard.svelte';
		import ChainDendrogram from '$components/breeding/ChainDendrogram.svelte';
		import GraphView from '$components/breeding/GraphView.svelte';
		import BreedingSidePanel from '$components/breeding/BreedingSidePanel.svelte';
		import type { TreeNode } from '$lib/breeding/dendrogram/types';
		import { directToTreeNode, chainToTree } from '$lib/breeding/dendrogram/treeBuilder';
		import type {
			BreedablePal, Chain as ChainT, ChainResponse, ChainRequest, ChainSource,
			DirectChildResponse, DirectParentsResponse, DirectPartnersResponse, DirectResultItem, PlayerSummary,
		} from '$types/index';

	  type Mode = 'direct' | 'selection' | 'save';
	  type DirectSub = 'forward' | 'reverse' | 'parents';

  let mode = $state<Mode>('direct');
  let directSub = $state<DirectSub>('forward');

  // shared pal metadata cache
  let pals = $state<BreedablePal[]>([]);
  let palMap = $state<Map<string, BreedablePal>>(new Map());
  let palsLoading = $state(true);
  // Passive-skill catalog (asset → display name). Loaded once so ChainCard
  // can resolve passive IDs ("CraftSpeed_up1" → "Serious") instead of
  // showing the raw asset string.
  let passiveMap = $state<Map<string, string>>(new Map());

  // direct mode inputs
  let parentA = $state<string | null>(null);
  let parentB = $state<string | null>(null);
  let directTarget = $state<string | null>(null);
	let directResult = $state<DirectChildResponse | null>(null);
	let partnersResult = $state<DirectPartnersResponse | null>(null);
	let parentsResult = $state<DirectParentsResponse | null>(null);

  // chain inputs (shared target + constraints)
  let chainTarget = $state<string | null>(null);
  let chainGender = $state<string | null>(null);
  let chainGens = $state(4);
  let chainMaxResults = $state(5);

  // selection-specific
  let selectedPool = $state<{ tribe: string; gender: string | null }[]>([]);

  // save-specific
  let players = $state<PlayerSummary[]>([]);
  let ownerUid = $state<string | null>(null);
  let ownerSearch = $state('');
  let ownerFocus = $state(false);
  let ownerBlurTimer: ReturnType<typeof setTimeout> | undefined;
  let includeWild = $state(false);

  // results
  let chains = $state<ChainT[]>([]);
  let chainElapsedMs = $state<number | null>(null);
  let chainWarnings = $state<string[]>([]);
  let computing = $state(false);
  let directLoading = $state(false);
  let error = $state<string | null>(null);

  // chain results view toggle (List vs Dendrogram). Always starts at 'list' on
  // a fresh page load — if we persisted 'graph' and the user reloaded before
  // running a search, they'd see an empty page (no overlay, no list, since
  // the overlay only renders when chains exist). The toggle is always visible
  // in the header, so re-selecting graph after a search is one click.
	  type ChainViewMode = 'list' | 'graph';
	  let chainViewMode = $state<ChainViewMode>('list');

	  // Graph mode: which chain result is active, and which node is selected.
	  let activeChainIndex = $state(0);
	  let selectedTreeNode = $state<TreeNode | null>(null);

	  // Derived detail object for the side panel.
	  type NodeDetail = {
	    id: string; tribe: string; display: string; icon: string | null;
	    gender?: string | null; passives: string[];
	    sourceType?: string; isBred: boolean; isTarget?: boolean; stepIndex?: number;
	  };
	  const selectedNodeDetail = $derived.by<NodeDetail | null>(() => {
	    const n = selectedTreeNode;
	    if (!n) return null;
	    return {
	      id: n.id, tribe: n.tribe, display: n.display, icon: n.icon,
	      gender: n.gender, passives: n.passives,
	      sourceType: n.sourceType, isBred: n.isBred, isTarget: n.isTarget,
	      stepIndex: n.stepIndex,
	    };
	  });

		  // Graph mode: per-gen / all-in-one toggle.
		  type GraphLayout = 'all-in-one' | 'per-gen';
		  let graphLayout = $state<GraphLayout>('all-in-one');
		  let currentGen = $state(1);
		  let sidePanelCollapsed = $state(false);

		  // Build TreeNode arrays for graph mode from chains or direct results.
		  const chainTrees = $derived<TreeNode[]>(
		    chains.map((c) => {
		      const depth = graphLayout === 'per-gen' ? currentGen : undefined;
		      return chainToTree(c, palMap, depth);
		    }),
		  );
		  const maxDepth = $derived(
		    chains.length > 0 ? Math.max(...chains.map((c) => c.generations)) : 1,
		  );

		  // Direct mode graph trees.
		  const directTrees = $derived.by<TreeNode[]>(() => {
		    if (directSub === 'forward' && directResult?.result) {
		      return [directToTreeNode(directResult.result, palMap)];
		    }
		    if (directSub === 'reverse' && partnersResult?.partners.length) {
		      return partnersResult.partners.map((p) => directToTreeNode(p, palMap));
		    }
		    if (directSub === 'parents' && parentsResult?.parents.length) {
		      return parentsResult.parents.map((p) => directToTreeNode(p, palMap));
		    }
		    return [];
		  });

			  // Reset active chain index when chains change (new search).
		  $effect(() => {
		    void chains.length;
		    activeChainIndex = 0;
		    selectedTreeNode = null;
		  });

  onMount(async () => {
    try {
      const [res, catalog] = await Promise.all([
        api.breedingPals(),
        api.palSkillCatalog().catch(() => ({ passives: [], actives: [] })),
      ]);
      pals = res.pals;
      palMap = new Map(res.pals.map((p) => [p.tribe, p]));
      // Build a passive asset→name lookup for ChainCard rendering.
      passiveMap = new Map(
        catalog.passives.map((p) => [String(p.asset).toLowerCase(), p.name]),
      );
    } finally {
      palsLoading = false;
    }
  });

  /** Resolve a passive asset ID to its display name (falls back to the raw id). */
  function passiveName(asset: string): string {
    return passiveMap.get(String(asset).toLowerCase()) ?? asset;
  }

  // Load the player list when entering save mode (needs a save).
  let playersLoaded = $state(false);
  async function ensurePlayers() {
    if (playersLoaded || !$saveLoaded) return;
    try {
      // Fetch all players (up to 500, covers any realistic server) instead
      // of the default 20, so the owner dropdown shows every player.
      const res = await api.players({ limit: 500 });
      players = res.players;
      playersLoaded = true;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  const tabs: { id: Mode; labelKey: string; icon: string }[] = [
    { id: 'direct', labelKey: 'web.breeding.tabs.direct', icon: 'lucide:arrow-right-left' },
    { id: 'selection', labelKey: 'web.breeding.tabs.selection', icon: 'lucide:list-checks' },
    { id: 'save', labelKey: 'web.breeding.tabs.save', icon: 'lucide:database' },
  ];

	  // ---- direct mode actions ----
	  async function runDirect() {
	    if (directSub === 'forward') {
	      if (!parentA || !parentB) return;
	      directLoading = true;
	      error = null;
	      try {
	        directResult = await api.breedingDirectChild({ parent_a: parentA, parent_b: parentB });
	      } catch (e) {
	        error = e instanceof Error ? e.message : String(e);
	      } finally {
	        directLoading = false;
	      }
	    } else if (directSub === 'reverse') {
	      if (!parentA || !directTarget) return;
	      directLoading = true;
	      error = null;
	      try {
	        partnersResult = await api.breedingDirectPartners({
	          parent_a: parentA,
	          target_child: directTarget,
	        });
	      } catch (e) {
	        error = e instanceof Error ? e.message : String(e);
	      } finally {
	        directLoading = false;
	      }
	    } else {
	      // parents — target only
	      if (!directTarget) return;
	      directLoading = true;
	      error = null;
	      try {
	        parentsResult = await api.breedingDirectParents({ target_child: directTarget });
	      } catch (e) {
	        error = e instanceof Error ? e.message : String(e);
	      } finally {
	        directLoading = false;
	      }
	    }
	  }

  // ---- chain actions (selection + save) ----
  async function runChain() {
    if (!chainTarget) return;
    computing = true;
    error = null;
    chains = [];
    chainWarnings = [];
    try {
      const req: ChainRequest = {
        target_pal: chainTarget,
        required_passives: [],
        target_gender: chainGender,
        max_generations: chainGens,
        max_results: chainMaxResults,
        mode: mode === 'save' ? 'save' : 'selection',
        ...(mode === 'save'
          ? { owner_uid: ownerUid, include_wild: includeWild }
          : {
              selected_pals: selectedPool.map((p) => ({
                species: p.tribe,
                gender: p.gender,
                passives: [],
              })),
            }),
      };
      const res: ChainResponse = await api.breedingChain(req);
      chains = res.chains;
      chainElapsedMs = res.elapsed_ms;
      chainWarnings = res.warnings;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      computing = false;
    }
  }

  function addToPool(tribe: string) {
    if (!selectedPool.some((p) => p.tribe === tribe)) {
      selectedPool = [...selectedPool, { tribe, gender: null }];
    }
  }
  function removeFromPool(tribe: string) {
    selectedPool = selectedPool.filter((p) => p.tribe !== tribe);
  }
  function setPoolGender(tribe: string, gender: string | null) {
    selectedPool = selectedPool.map((p) => (p.tribe === tribe ? { ...p, gender } : p));
  }

  // Clear stale results when switching modes/sub-modes.
  function switchMode(m: Mode) {
    mode = m;
    error = null;
    if (m === 'save') ensurePlayers();
  }
	  $effect(() => {
	    // re-run when directSub changes
	    void directSub;
	    directResult = null;
	    partnersResult = null;
	    parentsResult = null;
	  });

	  const canRunDirect = $derived(
	    directSub === 'forward'
	      ? !!(parentA && parentB)
	      : directSub === 'reverse'
	        ? !!(parentA && directTarget)
	        : !!directTarget  // parents — only need target
	  );
  const canRunChain = $derived(
    !!chainTarget && (mode === 'save' || selectedPool.length > 0) && (mode !== 'save' || $saveLoaded)
  );
  // Client-side fuzzy filter for the owner search.
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

		<div class="p-6 space-y-5 animate-fade-in {chainViewMode === 'graph' ? 'max-w-full px-4 flex flex-col h-full min-h-0' : 'max-w-5xl mx-auto'}">
  <!-- header -->
  <div class="flex items-center justify-between gap-3 flex-wrap">
    <div class="flex items-center gap-2">
      <Icon icon="lucide:git-merge" width={20} class="text-accent" />
      <h1 class="text-xl font-bold heading-gradient">{$t('web.breeding.title')}</h1>
    </div>
	    {#if chainElapsedMs !== null}
	      <span class="text-xs text-ink-dim font-mono">{chainElapsedMs}ms</span>
	    {/if}
  </div>

	  <!-- tab pills + list/graph toggle -->
	  <div class="flex gap-1.5 items-center">
	    {#each tabs as tab}
	      <button
	        class="flex items-center gap-1.5 px-3.5 py-2 rounded-4 text-sm font-medium transition-all {mode === tab.id
	          ? 'bg-accent/15 text-accent border border-accent/40'
	          : 'text-ink-secondary hover:bg-bg-hover border border-transparent'}"
	        onclick={() => switchMode(tab.id)}
	      >
	        <Icon icon={tab.icon} width={15} />
	        {$t(tab.labelKey)}
	      </button>
	    {/each}
	    <!-- List/Graph toggle on the far right -->
	    <div class="flex gap-1 p-0.5 rounded-4 bg-bg-deep/50 border border-line/40 ml-auto" role="group" aria-label="View mode">
	      <button
	        class="flex items-center gap-1 px-2.5 py-1 rounded-4 text-[11px] font-medium transition-all {chainViewMode === 'list'
	          ? 'bg-accent/15 text-accent border border-accent/40'
	          : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
	        onclick={() => (chainViewMode = 'list')}
	        title={$t('web.breeding.view_list')}
	      >
	        <Icon icon="lucide:list" width={12} />
	        {$t('web.breeding.view_list')}
	      </button>
	      <button
	        class="flex items-center gap-1 px-2.5 py-1 rounded-4 text-[11px] font-medium transition-all {chainViewMode === 'graph'
	          ? 'bg-accent/15 text-accent border border-accent/40'
	          : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
	        onclick={() => (chainViewMode = 'graph')}
	        title={$t('web.breeding.view_graph')}
	      >
	        <Icon icon="lucide:git-merge" width={12} />
	        {$t('web.breeding.view_graph')}
	      </button>
	    </div>
	  </div>

		  <!-- body -->
		  <div class="{chainViewMode === 'graph' ? 'flex-1 min-h-0 flex flex-col' : ''}">
		    {#if palsLoading}
		      <div class="flex justify-center py-12"><Spinner /></div>
		    {:else}
		      {#if mode === 'direct' && chainViewMode === 'list'}
	      <!-- ───── DIRECT MODE (LIST VIEW) ───── -->
      <div class="space-y-4">
	        <div class="flex gap-1.5">
	          {#each [{ id: 'forward', label: 'web.breeding.parent_a_b' }, { id: 'reverse', label: 'web.breeding.parent_a_target' }, { id: 'parents', label: 'web.breeding.target_only' }] as sub}
	            <button
	              class="px-3.5 py-1.5 rounded-4 text-xs font-medium transition-all {directSub === sub.id
	                ? 'bg-bg-hover text-ink-primary border border-line/60'
	                : 'text-ink-dim hover:text-ink-secondary border border-transparent'}"
	              onclick={() => (directSub = sub.id as DirectSub)}
	            >
	              {$t(sub.label)}
	            </button>
	          {/each}
	        </div>

	        <div class="card space-y-3">
	          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
	            {#if directSub !== 'parents'}
	              <div>
	                <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
	                  {$t('web.breeding.parent_a')}
	                </span>
	                <PalPicker value={parentA} onselect={(t) => (parentA = t)} />
	              </div>
	            {/if}
	            {#if directSub === 'forward'}
	              <div>
	                <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
	                  {$t('web.breeding.parent_b')}
	                </span>
	                <PalPicker value={parentB} onselect={(t) => (parentB = t)} exclude={parentA ? [parentA] : []} />
	              </div>
	            {:else if directSub === 'reverse' || directSub === 'parents'}
	              <div>
	                <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
	                  {$t('web.breeding.target_child')}
	                </span>
	                <PalPicker value={directTarget} onselect={(t) => (directTarget = t)} />
	              </div>
	            {/if}
          </div>
          <button class="btn btn-primary text-sm" disabled={!canRunDirect || directLoading} onclick={runDirect}>
            {#if directLoading}<Spinner size={16} />{:else}<Icon icon="lucide:play" width={15} />{/if}
            {$t('web.breeding.compute')}
          </button>
        </div>

        {#if error}<p class="text-xs text-rose-400">{error}</p>{/if}

        {#if directSub === 'forward' && directResult}
          <div class="space-y-2">
            <h3 class="text-xs font-semibold text-ink-dim uppercase tracking-wider">{$t('web.breeding.result')}</h3>
            {#if directResult.result}
              <DirectResult result={directResult.result} {palMap} />
            {:else}
              <EmptyState icon="lucide:ban" title={$t('web.breeding.no_combo')} />
            {/if}
          </div>
        {/if}

	        {#if directSub === 'reverse' && partnersResult}
	          <div class="space-y-2">
	            <h3 class="text-xs font-semibold text-ink-dim uppercase tracking-wider">
	              {$t('web.breeding.partners')} ({partnersResult.partners.length})
	            </h3>
	            {#if partnersResult.partners.length}
	              <div class="space-y-1.5">
	                {#each partnersResult.partners as p}
	                  <DirectResult result={p} {palMap} />
	                {/each}
	              </div>
	            {:else}
	              <EmptyState icon="lucide:ban" title={$t('web.breeding.no_combo')} />
	            {/if}
	          </div>
	        {/if}

	        {#if directSub === 'parents' && parentsResult}
	          <div class="space-y-2">
	            <h3 class="text-xs font-semibold text-ink-dim uppercase tracking-wider">
	              {$t('web.breeding.partners')} ({parentsResult.parents.length})
	            </h3>
	            {#if parentsResult.parents.length}
	              <div class="space-y-1.5">
	                {#each parentsResult.parents as p}
	                  <DirectResult result={p} {palMap} />
	                {/each}
	              </div>
	            {:else}
	              <EmptyState icon="lucide:ban" title={$t('web.breeding.no_combo')} />
	            {/if}
	          </div>
		        {/if}
	      </div>
	        {:else if mode === 'direct' && chainViewMode === 'graph'}
	        <!-- ───── DIRECT MODE (GRAPH VIEW) ───── -->
	        {#if error && !directTrees.length}
	          <p class="text-xs text-rose-400 mb-2">{error}</p>
	        {/if}
	        <div class="flex gap-4 flex-1 min-h-0">
	          <div class="flex-1 min-w-0 min-h-0 rounded-6 border border-line/30 bg-bg-deep/20 overflow-hidden">
	            {#if directTrees.length}
	              <GraphView
	                trees={directTrees}
	                {palMap}
	                {passiveName}
	                activeIndex={activeChainIndex}
	                onactiveIndexChange={(idx) => (activeChainIndex = idx)}
	                graphLayout={'all-in-one'}
	                maxDepth={1}
	                onselect={(node) => (selectedTreeNode = node)}
	              />
	            {:else}
	              <div class="flex-1 flex items-center justify-center h-full text-xs text-ink-dim italic">
	                Select parents in the side panel and click Compute
	              </div>
	            {/if}
	          </div>
	          <div class="w-64 shrink-0">
	            <div class="rounded-8 border border-line/20 bg-bg-card/90 shadow-card-lg overflow-hidden h-full backdrop-blur-sm">
	              <BreedingSidePanel
	                mode="direct"
	                chains={[]}
	                activeChainIndex={0}
	                directSub={directSub}
	                ondirectSubChange={(s) => (directSub = s as 'forward' | 'reverse' | 'parents')}
	                parentA={parentA}
	                onparentAChange={(t) => (parentA = t)}
	                parentB={parentB}
	                onparentBChange={(t) => (parentB = t)}
	                directTarget={directTarget}
	                ondirectTargetChange={(t) => (directTarget = t)}
	                canRunDirect={canRunDirect}
	                directLoading={directLoading}
	                oncomputeDirect={runDirect}
	                chainTarget={null}
	                chainGender={null}
	                chainGens={chainGens}
	                chainMaxResults={chainMaxResults}
	                selectedPool={selectedPool}
	                players={[]}
	                ownerUid={null}
	                includeWild={false}
	                saveLoaded={false}
	                computing={false}
	                canRunChain={false}
	                error={error}
	                {palMap}
	                {passiveName}
	                selectedNode={selectedNodeDetail}
	                collapsed={sidePanelCollapsed}
	                oncollapsedChange={(v) => (sidePanelCollapsed = v)}
	              />
	            </div>
	          </div>
	        </div>
	      {:else if chainViewMode === 'list'}
          <!-- ══════ LIST MODE (unchanged) ══════ -->
          <div class="space-y-4">
            {#if mode === 'save' && !$saveLoaded}
              <EmptyState icon="lucide:database" title={$t('web.breeding.save_required')}>
                <p class="text-xs">{$t('web.breeding.save_required_hint')}</p>
              </EmptyState>
            {:else}
              <div class="card space-y-3">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                      {$t('web.breeding.target')}
                    </span>
                    <PalPicker value={chainTarget} onselect={(t) => (chainTarget = t)} />
                  </div>
                  <div>
                    <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                      {$t('web.breeding.gender')}
                    </span>
                    <select bind:value={chainGender} class="input text-xs">
                      <option value={null}>{$t('web.breeding.any_gender')}</option>
                      <option value="Male">{$t('web.breeding.male')}</option>
                      <option value="Female">{$t('web.breeding.female')}</option>
                    </select>
                  </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                      {$t('web.breeding.max_generations')}
                    </span>
                    <input type="number" min="1" max="6" bind:value={chainGens} class="input text-xs" />
                  </div>
                  <div>
                    <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                      {$t('web.breeding.max_results')}
                    </span>
                    <input type="number" min="1" max="10" bind:value={chainMaxResults} class="input text-xs" />
                  </div>
                </div>

                {#if mode === 'selection'}
                  <div>
                    <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                      {$t('web.breeding.pool')} ({selectedPool.length})
                    </span>
                    <PalPicker
                      placeholder={$t('web.breeding.add_to_pool')}
                      onselect={(t) => addToPool(t)}
                      exclude={selectedPool.map((p) => p.tribe)}
                    />
                    {#if selectedPool.length}
                      <div class="flex flex-wrap gap-1.5 mt-2">
                        {#each selectedPool as member}
                          <div class="flex items-center gap-1 px-1.5 py-0.5 rounded-4 bg-bg-deep/50 border border-line/30">
                            <PalSlot tribe={member.tribe} display={palMap.get(member.tribe)?.display_name} icon={palMap.get(member.tribe)?.icon} size="sm" />
                            <select
                              class="bg-transparent text-[9px] text-ink-dim outline-none cursor-pointer"
                              value={member.gender ?? ''}
                              onchange={(e) => setPoolGender(member.tribe, (e.currentTarget as HTMLSelectElement).value || null)}
                            >
                              <option value="">Any</option>
                              <option value="Male">M</option>
                              <option value="Female">F</option>
                            </select>
                            <button class="text-ink-dim hover:text-rose-400 transition-fast" onclick={() => removeFromPool(member.tribe)} title="Remove">
                              <Icon icon="lucide:x" width={11} />
                            </button>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <span class="block text-[11px] font-semibold text-ink-dim uppercase tracking-wider mb-1">
                        {$t('web.breeding.owner')}
                      </span>
                      <!-- Searchable owner selector with real-time fuzzy filtering -->
                      <div class="relative">
                        <input
                          type="text"
                          class="input text-xs"
                          value={ownerUid
                            ? players.find((p) => p.uid === ownerUid)?.name ?? ownerUid
                            : ownerSearch}
                          placeholder={$t('web.breeding.owner_search')}
                          oninput={(e) => {
                            ownerSearch = (e.currentTarget as HTMLInputElement).value;
                            if (ownerUid) ownerUid = null;
                          }}
                          onfocus={() => {
                            if (ownerBlurTimer) clearTimeout(ownerBlurTimer);
                            ownerFocus = true;
                          }}
                          onblur={() => {
                            ownerBlurTimer = setTimeout(() => { ownerFocus = false; }, 200);
                          }}
                        />
                        {#if ownerFocus}
                          <div
                            class="absolute left-0 right-0 z-20 mt-1 max-h-48 overflow-y-auto rounded-6 border border-line/40 bg-bg-deep shadow-card-lg"
                            role="listbox"
                          >
                            <button
                              class="w-full text-left px-3 py-1.5 text-xs text-ink-muted hover:bg-bg-hover transition-fast border-b border-line/20 last:border-b-0 {ownerUid === null ? 'bg-accent/10' : ''}"
                              onmousedown={() => { ownerUid = null; ownerSearch = ''; ownerFocus = false; }}
                            >
                              {$t('web.breeding.all_players')}
                            </button>
                            {#each filteredPlayers as pl}
                              <button
                                class="w-full text-left px-3 py-1.5 text-xs text-ink-primary hover:bg-bg-hover transition-fast border-b border-line/20 last:border-b-0 {ownerUid === pl.uid ? 'bg-accent/10' : ''}"
                                onmousedown={() => { ownerUid = pl.uid; ownerSearch = ''; ownerFocus = false; }}
                              >
                                {pl.name}
                                <span class="text-ink-dim ml-1">({pl.pal_count} pals{pl.guild_name ? `, ${pl.guild_name}` : ''})</span>
                              </button>
                            {/each}
                            {#if filteredPlayers.length === 0 && ownerSearch}
                              <div class="px-3 py-2 text-xs text-ink-dim">{$t('web.breeding.owner_no_match')}</div>
                            {/if}
                          </div>
                        {/if}
                      </div>
                    </div>
                    <div class="flex items-end">
                      <label class="flex items-center gap-2 text-xs text-ink-secondary cursor-pointer">
                        <input type="checkbox" bind:checked={includeWild} class="accent-accent" />
                        {$t('web.breeding.include_wild')}
                      </label>
                    </div>
                  </div>
                {/if}

                <button class="btn btn-primary text-sm" disabled={!canRunChain || computing} onclick={runChain}>
                  {#if computing}<Spinner size={16} />{:else}<Icon icon="lucide:route" width={15} />{/if}
                  {$t('web.breeding.find_chains')}
                </button>
              </div>

              {#if error}<p class="text-xs text-rose-400">{error}</p>{/if}
              {#each chainWarnings as w}
                <p class="text-xs text-amber-400 flex items-center gap-1">
                  <Icon icon="lucide:alert-triangle" width={13} />{w}
                </p>
              {/each}

              {#if chains.length}
                <div class="space-y-3">
                  <h3 class="text-xs font-semibold text-ink-dim uppercase tracking-wider">
                    {$t('web.breeding.chains')} ({chains.length})
                  </h3>
                  {#each chains as chain (chains.indexOf(chain))}
                    <ChainCard {chain} {palMap} {passiveName} />
                  {/each}
                </div>
              {:else if !computing && chainElapsedMs !== null}
                <EmptyState icon="lucide:search-x" title={$t('web.breeding.no_chains')} />
              {/if}
            {/if}
          </div>

	        {:else}
	          <!-- ══════ CHAIN GRAPH MODE ══════ -->
	          {#if mode === 'save' && !$saveLoaded}
	            <EmptyState icon="lucide:database" title={$t('web.breeding.save_required')}>
	              <p class="text-xs">{$t('web.breeding.save_required_hint')}</p>
	            </EmptyState>
	          {:else}
	            {#if error}<p class="text-xs text-rose-400">{error}</p>{/if}
	            {#each chainWarnings as w}
	              <p class="text-xs text-amber-400 flex items-center gap-1">
	                <Icon icon="lucide:alert-triangle" width={13} />{w}
	              </p>
	            {/each}

	            <div class="flex gap-4 flex-1 min-h-0">
	              <!-- Left: graph -->
	              <div class="flex-1 min-w-0 min-h-0 rounded-6 border border-line/30 bg-bg-deep/20 overflow-hidden">
	                <GraphView
	                  trees={chainTrees}
	                  {chains}
	                  {palMap}
	                  {passiveName}
	                  activeIndex={activeChainIndex}
	                  onactiveIndexChange={(idx) => (activeChainIndex = idx)}
	                  graphLayout={graphLayout}
	                  ongraphLayoutChange={(v) => (graphLayout = v)}
	                  currentGen={currentGen}
	                  oncurrentGenChange={(v) => (currentGen = v)}
	                  maxDepth={maxDepth}
	                  onselect={(node) => (selectedTreeNode = node)}
	                />
	              </div>
	              <!-- Right: side panel (collapsible) -->
	              <div class="{sidePanelCollapsed ? 'w-10' : 'w-80'} shrink-0 transition-all duration-200">
	                <div class="rounded-8 border border-line/20 bg-bg-card/90 shadow-card-lg overflow-hidden h-full backdrop-blur-sm">
	                  <BreedingSidePanel
	                    mode={mode === 'save' ? 'save' : 'selection'}
	                    collapsed={sidePanelCollapsed}
	                    oncollapsedChange={(v) => (sidePanelCollapsed = v)}
	                    {chains}
	                    activeChainIndex={activeChainIndex}
	                    onactiveChainIndexChange={(idx) => (activeChainIndex = idx)}
	                    chainTarget={chainTarget}
	                    onchainTargetChange={(t) => (chainTarget = t)}
	                    chainGender={chainGender}
	                    onchainGenderChange={(g) => (chainGender = g)}
	                    chainGens={chainGens}
	                    onchainGensChange={(n) => (chainGens = n)}
	                    chainMaxResults={chainMaxResults}
	                    onchainMaxResultsChange={(n) => (chainMaxResults = n)}
	                    selectedPool={selectedPool}
	                    onaddToPool={(t) => addToPool(t)}
	                    onremoveFromPool={(t) => removeFromPool(t)}
	                    onsetPoolGender={(t, g) => setPoolGender(t, g)}
	                    {players}
	                    ownerUid={ownerUid}
	                    onownerUidChange={(uid) => (ownerUid = uid)}
	                    includeWild={includeWild}
	                    onincludeWildChange={(val) => (includeWild = val)}
	                    saveLoaded={$saveLoaded}
	                    computing={computing}
	                    canRunChain={canRunChain}
	                    oncompute={runChain}
	                    error={error}
	                    {palMap}
	                    {passiveName}
	                    selectedNode={selectedNodeDetail}
	                  />
	                </div>
	              </div>
	            </div>
	          {/if}
	        {/if}
	      {/if}
    </div>
  </div>
