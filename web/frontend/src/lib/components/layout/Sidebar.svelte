<script lang="ts">
  import { page } from '$app/stores';
  import { saveLoaded } from '$stores/index';
  import Icon from '@iconify/svelte';

  interface NavItem { href: string; label: string; icon: string; needsSave?: boolean; }
  interface NavGroup { label: string; items: NavItem[]; }

  const groups: NavGroup[] = [
    {
      label: 'Tools',
      items: [
        { href: '/', label: 'Overview', icon: 'lucide:wrench' },
        { href: '/tools', label: 'All Tools', icon: 'lucide:wrench' },
        { href: '/players', label: 'Players', icon: 'lucide:users', needsSave: true },
        { href: '/guilds', label: 'Guilds', icon: 'lucide:building-2', needsSave: true },
        { href: '/bases', label: 'Bases', icon: 'lucide:map-pin', needsSave: true },
        { href: '/map', label: 'Map', icon: 'lucide:map', needsSave: true },
      ],
    },
    {
      label: 'Editors',
      items: [
        { href: '/inventory', label: 'Player Inventory', icon: 'lucide:package', needsSave: true },
        { href: '/base-inventory', label: 'Base Inventory', icon: 'lucide:warehouse', needsSave: true },
        { href: '/pal-editor', label: 'Pal Editor', icon: 'lucide:pencil', needsSave: true },
      ],
    },
    {
      label: 'Utilities',
      items: [
        { href: '/containers', label: 'Containers', icon: 'lucide:box', needsSave: true },
        { href: '/exclusions', label: 'Exclusions', icon: 'lucide:shield-off', needsSave: true },
        { href: '/backups', label: 'Backups', icon: 'lucide:archive' },
        { href: '/settings', label: 'Settings', icon: 'lucide:settings' },
      ],
    },
    {
      label: 'Wiki',
      items: [
        { href: '/wiki', label: 'Game Reference', icon: 'lucide:book-open' },
      ],
    },
  ];

  function isActive(href: string): boolean {
    if (href === '/') return $page.url.pathname === '/';
    return $page.url.pathname.startsWith(href);
  }
</script>

<aside class="relative h-full w-56 shrink-0 flex flex-col bg-nav-gradient border-r border-line/50">
  <div class="flex items-center gap-2.5 px-4 h-14 border-b border-line/40 shrink-0">
    <div class="w-6 h-6 rounded-4 bg-cyber-gradient shrink-0 shadow-glow-cyan animate-breathe" style="background-size:200% 200%;animation:gradientShift 3s ease infinite;"></div>
    <span class="font-semibold text-sm tracking-wide heading-gradient">PalworldSaveTools</span>
  </div>

  <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-4">
    {#each groups as group}
      <div>
        <p class="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
          {group.label}
        </p>
        <div class="space-y-0.5">
          {#each group.items as item}
            <a
              href={item.href}
              class="nav-link {isActive(item.href) ? 'nav-link-active' : 'nav-link-inactive'}"
              class:opacity-40={item.needsSave && !$saveLoaded}
              title={item.needsSave && !$saveLoaded ? 'Load a save to enable' : item.label}
            >
              <Icon icon={item.icon} width={16} class="shrink-0" />
              <span class="truncate">{item.label}</span>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  </nav>

  <div class="px-3 py-3 border-t border-line/40 text-[10px] text-ink-dim">
    Read-only viewers · Editing in phase 2
  </div>
</aside>
