<script lang="ts">
  import { page } from '$app/stores';
  import Icon from '@iconify/svelte';
  import type { Snippet } from 'svelte';
  import { t } from '$stores/index';

  let { children }: { children: Snippet } = $props();

  const categories = [
    { labelKey: 'web.wiki.cat_pals', href: '/wiki/pals', icon: 'lucide:egg', id: 'pals' },
    { labelKey: 'web.wiki.cat_items', href: '/wiki/items', icon: 'lucide:package', id: 'items' },
    { labelKey: 'web.wiki.cat_buildings', href: '/wiki/buildings', icon: 'lucide:building-2', id: 'buildings' },
    { labelKey: 'web.wiki.cat_active_skills', href: '/wiki/active-skills', icon: 'lucide:swords', id: 'active-skills' },
    { labelKey: 'web.wiki.cat_passive_skills', href: '/wiki/passive-skills', icon: 'lucide:shield', id: 'passive-skills' },
    { labelKey: 'web.wiki.cat_technologies', href: '/wiki/technologies', icon: 'lucide:flask-conical', id: 'technologies' },
    { labelKey: 'web.wiki.cat_elements', href: '/wiki/elements', icon: 'lucide:flame', id: 'elements' },
    { labelKey: 'web.wiki.cat_work_suitability', href: '/wiki/work-suitability', icon: 'lucide:hammer', id: 'work-suitability' },
  ];

  const activeCategory = $derived.by(() => {
    const path: string = $page.url.pathname;
    if (path === '/wiki') return '';
    const match = categories.find((c) => path.startsWith(c.href));
    return match?.id || '';
  });
</script>

<div class="flex h-full">
  <aside class="w-48 shrink-0 flex flex-col gap-0.5 border-r-2 border-line/50 p-3 pt-4 bg-bg-deep/85">
    <a href="/wiki" class="nav-link {activeCategory === '' ? 'nav-link-active' : 'nav-link-inactive'} mb-2">
      <Icon icon="lucide:book-open" width={16} class="shrink-0" />
      <span class="text-xs font-semibold">{$t('web.wiki.home')}</span>
    </a>
    <p class="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-dim">{$t('web.wiki.categories')}</p>
    {#each categories as cat}
      <a
        href={cat.href}
        class="nav-link {activeCategory === cat.id ? 'nav-link-active' : 'nav-link-inactive'}"
      >
        <Icon icon={cat.icon} width={16} class="shrink-0" />
        <span class="truncate text-xs">{$t(cat.labelKey)}</span>
      </a>
    {/each}
  </aside>
  <div class="flex-1 overflow-y-auto p-5 bg-bg-base/80">
    {@render children()}
  </div>
</div>
