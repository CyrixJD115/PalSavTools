<script lang="ts">
  import { page } from '$app/stores';
  import { saveLoaded, t } from '$stores/index';
  import Icon from '@iconify/svelte';

  interface NavItem { href: string; labelKey: string; icon: string; needsSave?: boolean; }
  interface NavGroup { labelKey: string; items: NavItem[]; }

  const groups: NavGroup[] = [
    {
      labelKey: 'web.nav.tools',
      items: [
        { href: '/', labelKey: 'web.nav.overview', icon: 'lucide:wrench' },
        { href: '/tools', labelKey: 'web.nav.all_tools', icon: 'lucide:wrench' },
        { href: '/players', labelKey: 'web.nav.players', icon: 'lucide:users', needsSave: true },
        { href: '/guilds', labelKey: 'web.nav.guilds', icon: 'lucide:building-2', needsSave: true },
        { href: '/bases', labelKey: 'web.nav.bases', icon: 'lucide:map-pin', needsSave: true },
        { href: '/map', labelKey: 'web.nav.map', icon: 'lucide:map', needsSave: true },
        { href: '/breeding', labelKey: 'web.nav.breeding', icon: 'lucide:git-merge' },
      ],
    },
    {
      labelKey: 'web.nav.editors',
      items: [
        { href: '/inventory', labelKey: 'web.nav.player_inventory', icon: 'lucide:package', needsSave: true },
        { href: '/base-inventory', labelKey: 'web.nav.base_inventory', icon: 'lucide:warehouse', needsSave: true },
        { href: '/pal-editor', labelKey: 'web.nav.pal_editor', icon: 'lucide:pencil', needsSave: true },
      ],
    },
    {
      labelKey: 'web.nav.utilities',
      items: [
        { href: '/containers', labelKey: 'web.nav.containers', icon: 'lucide:box', needsSave: true },
        { href: '/exclusions', labelKey: 'web.nav.exclusions', icon: 'lucide:shield-off', needsSave: true },
        { href: '/backups', labelKey: 'web.nav.backups', icon: 'lucide:archive' },
        { href: '/settings', labelKey: 'web.nav.settings', icon: 'lucide:settings' },
      ],
    },
    {
      labelKey: 'web.nav.wiki',
      items: [
        { href: '/wiki', labelKey: 'web.nav.game_reference', icon: 'lucide:book-open' },
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
    <span class="font-semibold text-sm tracking-wide heading-gradient">{$t('web.app.title')}</span>
  </div>

  <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-4">
    {#each groups as group}
      <div>
        <p class="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-dim">
          {$t(group.labelKey)}
        </p>
        <div class="space-y-0.5">
          {#each group.items as item}
            <a
              href={item.href}
              class="nav-link {isActive(item.href) ? 'nav-link-active' : 'nav-link-inactive'}"
              class:opacity-40={item.needsSave && !$saveLoaded}
              title={item.needsSave && !$saveLoaded ? $t('web.nav.load_to_enable') : $t(item.labelKey)}
            >
              <Icon icon={item.icon} width={16} class="shrink-0" />
              <span class="truncate">{$t(item.labelKey)}</span>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  </nav>

  <div class="px-3 py-3 border-t border-line/40 text-[10px] text-ink-dim">
    {$t('web.nav.footer')}
  </div>
</aside>
