<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { ToolInfo } from '$types/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import ToolGrid from '$lib/components/tools/ToolGrid.svelte';
  import ToolModal from '$lib/components/tools/ToolModal.svelte';

  let tools = $state<ToolInfo[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentTool = $state<ToolInfo | null>(null);
  let modalOpen = $state(false);

  async function load() {
    loading = true; error = null;
    try { tools = (await api.tools()).tools; }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(load);

  function onSelectTool(id: string) {
    const t = tools.find((t) => t.id === id);
    if (t) { currentTool = t; modalOpen = true; }
  }
</script>

<div class="p-6 max-w-6xl mx-auto space-y-4 animate-fade-in">
  <div class="flex items-center justify-between gap-4 mb-2">
    <div>
      <h1 class="text-xl font-bold heading-gradient">Tools</h1>
      <p class="text-xs text-ink-muted">{tools.length} tools available</p>
    </div>
  </div>

  {#if loading}
    <div class="flex justify-center py-12"><Spinner size={24} /></div>
  {:else if error}
    <div class="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-300">{error}</div>
  {:else}
    <ToolGrid {tools} onSelectTool={onSelectTool} />
  {/if}
</div>

<ToolModal
  tool={currentTool}
  open={modalOpen}
  onClose={() => { modalOpen = false; currentTool = null; }}
/>
