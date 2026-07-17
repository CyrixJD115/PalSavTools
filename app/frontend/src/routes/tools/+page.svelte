<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import type { ToolInfo } from '$types/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import ToolModal from '$lib/components/tools/ToolModal.svelte';
  import Icon from '@iconify/svelte';

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

  const iconMap: Record<string, string> = {
    FileSymlink: 'lucide:file-symlink',
    Hash: 'lucide:hash',
    PackagePlus: 'lucide:package-plus',
    Map: 'lucide:map',
    Wrench: 'lucide:wrench',
    Gamepad2: 'lucide:gamepad-2',
    FileArchive: 'lucide:file-archive',
    ArrowRightFromLine: 'lucide:arrow-right-from-line',
    UserRoundPlus: 'lucide:user-round-plus',
    Users: 'lucide:users',
    HardDrive: 'lucide:hard-drive',
  };

  const iconColors: Record<string, string> = {
    converting: 'text-sky-400',
    management: 'text-amber-400',
    utility: 'text-emerald-400',
  };
  const iconBgs: Record<string, string> = {
    converting: 'bg-sky-500/10',
    management: 'bg-amber-500/10',
    utility: 'bg-emerald-500/10',
  };
  const chipTones: Record<string, string> = {
    converting: 'chip-blue',
    management: 'chip-amber',
    utility: 'chip-green',
  };
</script>

<div class="p-4 max-w-6xl mx-auto animate-fade-in">
  <div class="flex items-baseline gap-3 mb-5">
    <h1 class="text-xl font-bold heading-gradient">{$t('web.tools.title')}</h1>
    <p class="text-xs text-ink-muted">{$t('web.tools.count', { count: tools.length })}</p>
  </div>

  {#if loading}
    <div class="flex justify-center py-12"><Spinner size={24} /></div>
  {:else if error}
    <div class="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-300">{error}</div>
  {:else}
    <div class="grid gap-4" style="grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));">
      {#each tools as tool (tool.id)}
        <button onclick={() => onSelectTool(tool.id)}
          class="card card-hover group flex flex-col items-center justify-center gap-2.5 p-5 aspect-square cursor-pointer text-center">
          <div class="w-12 h-12 rounded-xl {iconBgs[tool.category] ?? 'bg-surface-hover'} flex items-center justify-center">
            <Icon icon={iconMap[tool.icon] ?? 'lucide:wrench'} width={24} class={iconColors[tool.category] ?? 'text-ink-muted'} />
          </div>
          <div class="flex items-center gap-1.5">
            <span class="text-sm font-semibold text-ink-emphasis group-hover:text-accent transition-colors">{tool.name}</span>
            {#if tool.windows_only}
              <span class="text-[9px] bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded-full font-medium shrink-0">{$t('web.tools.windows_badge')}</span>
            {/if}
          </div>
          <p class="text-[11px] text-ink-muted leading-snug line-clamp-2">{tool.description}</p>
          <span class="chip {chipTones[tool.category] ?? 'chip-blue'} text-[9px]">{tool.category_label}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<ToolModal
  tool={currentTool}
  open={modalOpen}
  onClose={() => { modalOpen = false; currentTool = null; }}
/>
