<script lang="ts">
  import type { ToolInfo } from '$types/index';
  import Icon from '@iconify/svelte';
  let { tool, onSelect }: {
    tool: ToolInfo;
    onSelect: (id: string) => void;
  } = $props();

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

  let iconName = $derived(iconMap[tool.icon] ?? 'lucide:wrench');
</script>

<button
  class="card card-hover group cursor-pointer text-left w-full"
  class:opacity-50={tool.windows_only}
  onclick={() => onSelect(tool.id)}
>
  <div class="flex items-start gap-3 px-4 py-3">
    <div class="w-9 h-9 rounded-lg {iconBgs[tool.category] ?? 'bg-surface-hover'} flex items-center justify-center shrink-0 mt-0.5">
      <Icon icon={iconName} width={16} class="{iconColors[tool.category] ?? 'text-ink-muted'}" />
    </div>
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="font-semibold text-sm text-ink-emphasis group-hover:text-accent transition-colors truncate">
          {tool.name}
        </span>
        <div class="flex items-center gap-1.5 shrink-0">
          {#if tool.category === 'converting'}
            <span class="chip chip-blue text-[10px]">Converting</span>
          {:else if tool.category === 'management'}
            <span class="chip chip-amber text-[10px]">Management</span>
          {:else}
            <span class="chip chip-green text-[10px]">Utility</span>
          {/if}
          {#if tool.windows_only}
            <span class="chip text-[10px] bg-purple-500/10 text-purple-400">Windows</span>
          {/if}
        </div>
      </div>
      <p class="text-xs text-ink-muted mt-0.5 leading-relaxed">
        {tool.description}
      </p>
    </div>
  </div>
</button>
