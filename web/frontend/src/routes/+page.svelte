<script lang="ts">
  import { saveLoaded, saveSummary, saveCounts, loadingSave, saveState } from '$stores/index';
  import { api } from '$lib/api/client';
  import { toast } from '$stores/toast';
  import type { ToolInfo } from '$types/index';
  import Card from '$components/ui/Card.svelte';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import LoadSaveModal from '$components/layout/LoadSaveModal.svelte';
  import ToolModal from '$components/tools/ToolModal.svelte';
  import Icon from '@iconify/svelte';
  import TauriDropZone from '$components/drop/TauriDropZone.svelte'
  import { isTauri } from '$lib/tauri'

  let loadOpen = $state(false);
  let exporting = $state(false);
  let dragOver = $state(false);
  let winW = $state(0);
  let winH = $state(0);
  let toolModalOpen = $state(false);
  let currentTool = $state<ToolInfo | null>(null);

  $effect(() => {
    function upd() { winW = window.innerWidth; winH = window.innerHeight; }
    upd();
    addEventListener('resize', upd);
    return () => removeEventListener('resize', upd);
  });

  let tooSmall = $derived(winW > 0 && (winW < 800 || winH < 500));

  const quickTools: (ToolInfo & { icon: string })[] = [
    { id: 'convert', name: 'Convert SAV ↔ JSON', icon: 'lucide:file-symlink', category: 'converting', category_label: 'Converting', description: 'Convert between binary .sav and human-readable .json formats.', windows_only: false },
    { id: 'convert-ids', name: 'Steam ID ↔ Palworld UID', icon: 'lucide:hash', category: 'utility', category_label: 'Utility', description: 'Convert Steam IDs to Palworld UIDs and vice versa.', windows_only: false },
    { id: 'slot-injector', name: 'Slot Injector', icon: 'lucide:package-plus', category: 'management', category_label: 'Management', description: 'Increase pal container slot counts (max 960) across all player palboxes/parties.', windows_only: false },
    { id: 'restore-map', name: 'Restore Map', icon: 'lucide:map', category: 'management', category_label: 'Management', description: 'Clear fog of war and reveal hidden map locations.', windows_only: false },
  ];

  const catBgs: Record<string, string> = {
    converting: 'bg-sky-500/10',
    management: 'bg-amber-500/10',
    utility: 'bg-emerald-500/10',
  };
  const catColors: Record<string, string> = {
    converting: 'text-sky-400',
    management: 'text-amber-400',
    utility: 'text-emerald-400',
  };
  const chipTones: Record<string, string> = {
    converting: 'chip-blue',
    management: 'chip-amber',
    utility: 'chip-green',
  };

  async function doExport() {
    exporting = true;
    try {
      const { blob, filename, size } = await api.exportSave();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${filename} (${(size / 1024 / 1024).toFixed(1)} MB)`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Export failed');
    } finally {
      exporting = false;
    }
  }

  async function doUnload() {
    try {
      const res = await api.unload();
      saveState.set(res);
      toast.info('Save unloaded');
    } catch (e) {
      toast.error('Unload failed');
    }
  }

  function onQuickToolSelect(tool: ToolInfo) {
    currentTool = tool;
    toolModalOpen = true;
  }

  $effect(() => {
    function onEnter(e: DragEvent) {
      if (e.dataTransfer?.types?.includes('Files')) {
        e.preventDefault();
        dragOver = true;
      }
    }
    function onLeave(e: DragEvent) {
      if (!e.relatedTarget || !(document.body as Node).contains(e.relatedTarget as Node)) {
        dragOver = false;
      }
    }
    document.addEventListener('dragenter', onEnter);
    document.addEventListener('dragleave', onLeave);
    return () => {
      document.removeEventListener('dragenter', onEnter);
      document.removeEventListener('dragleave', onLeave);
    };
  });

  function onDragOver(e: DragEvent) {
    if (dragOver) e.preventDefault();
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (!file || !file.name.toLowerCase().endsWith('.sav')) return;
    loadingSave.set(true);
    try {
      const res = await api.uploadSave(file);
      saveState.set({ loaded: true, summary: res.summary, counts: res.counts });
      toast.success(`Loaded ${res.summary.filename} from drop`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      loadingSave.set(false);
    }
  }

  async function onTauriDrop(paths: string[]) {
    const file = paths[0]
    if (!file || !file.toLowerCase().endsWith('.sav')) return
    loadingSave.set(true)
    try {
      const res = await api.loadFromPath(file)
      saveState.set({ loaded: true, summary: res.summary, counts: res.counts })
      toast.success(`Loaded ${res.summary.filename} from drop`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Load failed')
    } finally {
      loadingSave.set(false)
    }
  }

  function fmtBytes(n: number): string {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(n) / Math.log(1024));
    return `${(n / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`;
  }

  const stats = $derived([
    { label: 'Guilds', value: $saveCounts?.guilds ?? 0, icon: 'lucide:building-2', href: '/guilds' },
    { label: 'Players', value: $saveCounts?.players ?? 0, icon: 'lucide:users', href: '/players' },
    { label: 'Bases', value: $saveCounts?.bases ?? 0, icon: 'lucide:map-pin', href: '/bases' },
    { label: 'Containers', value: $saveCounts?.containers ?? 0, icon: 'lucide:box', href: '/containers' },
    { label: 'Pals', value: $saveCounts?.pals ?? 0, icon: 'lucide:sparkles', href: '/pal-editor' },
  ]);
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && dragOver && (dragOver = false)} />

  <!-- resize warning -->
{#if tooSmall}
  <div class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg-base animate-fade-in">
    <Icon icon="lucide:monitor-warning" width={48} class="text-amber-400 mb-3" />
    <h2 class="text-lg font-bold text-ink-emphasis mb-1">Window Too Small</h2>
    <p class="text-xs text-ink-muted text-center max-w-xs">
      Please resize to at least <span class="text-ink-secondary font-medium">800×500</span> px.
    </p>
  </div>
{/if}

<TauriDropZone onFilesDrop={onTauriDrop}>

<!-- drag-and-drop overlay -->
{#if dragOver}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg-base/90 backdrop-blur-sm animate-fade-in"
    ondrop={onDrop} ondragover={(e) => e.preventDefault()}>
    <div class="w-60 h-60 rounded-2xl border-2 border-dashed border-status-success/60 flex flex-col items-center justify-center gap-2 bg-bg-elevated/80">
      <Icon icon="lucide:upload" width={40} class="text-status-success" />
      <span class="text-base font-bold text-status-success">Drop Level.sav</span>
      <span class="text-xs text-ink-muted">to load this save file</span>
    </div>
    <button class="mt-4 text-xs text-ink-dim hover:text-ink-secondary underline" onclick={() => (dragOver = false)}>
      Cancel
    </button>
  </div>
{/if}

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="p-4 max-w-5xl mx-auto space-y-4 animate-fade-in min-h-[calc(100vh-3.5rem)]"
  ondragover={onDragOver} ondrop={onDrop}>
  <div>
    <h1 class="text-xl font-bold heading-gradient">Overview</h1>
    <p class="text-xs text-ink-muted mt-0.5">
      Load a Palworld save to inspect its contents.
    </p>
  </div>

  <Card>
    {#if !$saveLoaded}
      <div class="flex flex-col items-center gap-2 py-3">
        <Icon icon="lucide:folder-open" width={28} class="text-accent" />
        <span class="text-sm font-semibold text-ink-secondary">No Save Loaded</span>
        <Button variant="primary" onclick={() => (loadOpen = true)} disabled={$loadingSave}>
          <Icon icon="lucide:folder-open" width={16} /> Load Save
        </Button>
        <span class="text-xs text-ink-dim">or drag & drop a Level.sav file here</span>
      </div>
    {:else}
      <div class="flex flex-wrap items-center gap-2">
        <Button variant="primary" onclick={() => (loadOpen = true)} disabled={$loadingSave}>
          <Icon icon="lucide:folder-open" width={16} /> Load Another
        </Button>
        <Button variant="secondary" onclick={doExport} disabled={exporting}>
          <Icon icon="lucide:download" width={16} /> Export .sav
        </Button>
        <Button variant="ghost" onclick={doUnload}>
          <Icon icon="lucide:log-out" width={16} /> Unload
        </Button>
        <div class="flex-1"></div>
        {#if $saveSummary}
          <Badge tone="accent">type {$saveSummary.save_type}</Badge>
          <Badge tone="neutral">{$saveSummary.class_name}</Badge>
        {/if}
      </div>
    {/if}
  </Card>

  {#if $saveLoaded}
    <div>
      <h2 class="text-xs font-semibold text-ink-secondary uppercase tracking-wider mb-2">World Summary</h2>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        {#each stats as s}
          <a href={s.href} class="card card-hover flex flex-col gap-1.5 group animate-fade-in">
            <div class="flex items-center justify-between">
              <Icon icon={s.icon} width={16} class="text-accent" />
              <Icon icon="lucide:arrow-right" width={12} class="text-ink-dim group-hover:text-accent transition-fast" />
            </div>
            <div>
              <p class="text-xl font-bold text-ink-emphasis tabular-nums">{s.value}</p>
              <p class="text-xs text-ink-muted uppercase tracking-wide">{s.label}</p>
            </div>
          </a>
        {/each}
      </div>
    </div>

    <Card title="Loaded File">
      <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
        <div class="flex justify-between py-1 border-b border-line/30">
          <dt class="text-ink-muted text-xs">Filename</dt>
          <dd class="text-ink-primary font-mono text-xs">{$saveSummary?.filename}</dd>
        </div>
        <div class="flex justify-between py-1 border-b border-line/30">
          <dt class="text-ink-muted text-xs">File size</dt>
          <dd class="text-ink-primary tabular-nums text-xs">{fmtBytes($saveSummary?.file_size ?? 0)}</dd>
        </div>
        <div class="flex justify-between py-1 border-b border-line/30">
          <dt class="text-ink-muted text-xs">Save directory</dt>
          <dd class="text-ink-secondary font-mono text-xs truncate max-w-[200px]">{$saveSummary?.save_dir}</dd>
        </div>
        <div class="flex justify-between py-1 border-b border-line/30">
          <dt class="text-ink-muted text-xs">Compression</dt>
          <dd class="text-ink-primary text-xs">
            {$saveSummary?.save_type === 50 ? 'PLZ (double-zlib)' : 'PLM (Oodle)'}
          </dd>
        </div>
      </dl>
    </Card>
  {:else}
    <Card>
      <EmptyState icon="lucide:file-x" title="No save loaded">
        <p>Click <strong class="text-ink-secondary">Load Save</strong> and point to your
        <code class="text-accent-light">Level.sav</code> to begin.</p>
      </EmptyState>
    </Card>
  {/if}

  <!-- Quick Tools -->
  <div>
    <div class="flex items-center gap-2 mb-2">
      <h2 class="text-xs font-semibold text-ink-secondary uppercase tracking-wider">Quick Tools</h2>
      <span class="text-[10px] text-ink-dim">— 4 most used</span>
    </div>
    <div class="grid grid-cols-2 gap-2">
      {#each quickTools as tool}
        <button onclick={() => onQuickToolSelect(tool)} class="card card-hover group flex items-start gap-2.5 px-3 py-2.5 cursor-pointer text-left w-full">
          <div class="w-8 h-8 rounded-lg {catBgs[tool.category] ?? 'bg-surface-hover'} flex items-center justify-center shrink-0 mt-0.5">
            <Icon icon={tool.icon} width={16} class={catColors[tool.category] ?? 'text-ink-muted'} />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <span class="text-xs font-semibold text-ink-emphasis group-hover:text-accent transition-colors truncate">{tool.name}</span>
              <span class="chip {chipTones[tool.category] ?? 'chip-blue'} text-[9px] whitespace-nowrap shrink-0">{tool.category_label}</span>
            </div>
            <p class="text-[10px] text-ink-muted mt-0.5 leading-snug truncate">{tool.description}</p>
          </div>
        </button>
      {/each}
      <a href="/tools" class="card card-hover flex items-center justify-center gap-1.5 px-3 py-2.5 cursor-pointer col-span-2 border border-dashed border-line/40 hover:border-accent/40">
        <span class="text-xs text-ink-muted hover:text-accent transition-colors">View all tools</span>
        <Icon icon="lucide:arrow-right" width={14} class="text-ink-dim hover:text-accent transition-colors" />
      </a>
    </div>
  </div>
</div>

</TauriDropZone>

<ToolModal
  tool={currentTool}
  open={toolModalOpen}
  onClose={() => { toolModalOpen = false; currentTool = null; }}
/>

<LoadSaveModal bind:open={loadOpen} />
