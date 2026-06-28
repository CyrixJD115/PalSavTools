<script lang="ts">
  import { page } from '$app/stores';
  import Icon from '@iconify/svelte';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();

  const categories = [
    { label: 'Pals', href: '/wiki/pals', icon: 'lucide:egg', id: 'pals' },
    { label: 'Items', href: '/wiki/items', icon: 'lucide:package', id: 'items' },
    { label: 'Buildings', href: '/wiki/buildings', icon: 'lucide:building-2', id: 'buildings' },
    { label: 'Active Skills', href: '/wiki/active-skills', icon: 'lucide:swords', id: 'active-skills' },
    { label: 'Passive Skills', href: '/wiki/passive-skills', icon: 'lucide:shield', id: 'passive-skills' },
    { label: 'Technologies', href: '/wiki/technologies', icon: 'lucide:flask-conical', id: 'technologies' },
    { label: 'Elements', href: '/wiki/elements', icon: 'lucide:flame', id: 'elements' },
    { label: 'Work Suitability', href: '/wiki/work-suitability', icon: 'lucide:hammer', id: 'work-suitability' },
  ];

  const activeCategory = $derived.by(() => {
    const path: string = $page.url.pathname;
    if (path === '/wiki') return '';
    const match = categories.find((c) => path.startsWith(c.href));
    return match?.id || '';
  });
</script>

<div class="flex h-full">
  <aside class="w-48 shrink-0 flex flex-col gap-0.5 border-r-2 border-line/50 p-3 pt-4 bg-bg-deep/50">
    <a href="/wiki" class="nav-link {activeCategory === '' ? 'nav-link-active' : 'nav-link-inactive'} mb-2">
      <Icon icon="lucide:book-open" width={16} class="shrink-0" />
      <span class="text-xs font-semibold">Wiki Home</span>
    </a>
    <p class="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-dim">Categories</p>
    {#each categories as cat}
      <a
        href={cat.href}
        class="nav-link {activeCategory === cat.id ? 'nav-link-active' : 'nav-link-inactive'}"
      >
        <Icon icon={cat.icon} width={16} class="shrink-0" />
        <span class="truncate text-xs">{cat.label}</span>
      </a>
    {/each}
  </aside>
  <div class="flex-1 overflow-y-auto p-5">
    {@render children()}
  </div>
</div>
