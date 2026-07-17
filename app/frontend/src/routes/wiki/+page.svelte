<script lang="ts">
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';

  const categories = [
    { labelKey: 'web.wiki.cat_pals', href: '/wiki/pals', icon: 'lucide:egg', desc: 'Stats, elements, skills, and work suitabilities for all Pals.' },
    { labelKey: 'web.wiki.cat_items', href: '/wiki/items', icon: 'lucide:package', desc: 'All items including weapons, armor, consumables, and materials.' },
    { labelKey: 'web.wiki.cat_buildings', href: '/wiki/buildings', icon: 'lucide:building-2', desc: 'Building recipes, materials, and stats.' },
    { labelKey: 'web.wiki.cat_active_skills', href: '/wiki/active-skills', icon: 'lucide:swords', desc: 'Combat skills with element types, power, and cooldowns.' },
    { labelKey: 'web.wiki.cat_passive_skills', href: '/wiki/passive-skills', icon: 'lucide:shield', desc: 'Passive abilities and their stat effects.' },
    { labelKey: 'web.wiki.cat_technologies', href: '/wiki/technologies', icon: 'lucide:flask-conical', desc: 'Technology tree, unlock requirements, and costs.' },
    { labelKey: 'web.wiki.cat_elements', href: '/wiki/elements', icon: 'lucide:flame', desc: 'Element types and their properties.' },
    { labelKey: 'web.wiki.cat_work_suitability', href: '/wiki/work-suitability', icon: 'lucide:hammer', desc: 'Work types and which Pals excel at each.' },
  ];
</script>

<div class="space-y-5 animate-fadeInUp">
  <div>
    <h1 class="text-xl font-bold heading-gradient">{$t('web.wiki.home_title')}</h1>
    <p class="text-xs text-ink-muted mt-0.5">{$t('web.wiki.home_subtitle')}</p>
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {#each categories as cat}
      <a
        href={cat.href}
        class="card card-hover group flex flex-col gap-3 cursor-pointer"
      >
        <div class="w-10 h-10 rounded-lg bg-accent/10 border-2 border-accent/30 flex items-center justify-center group-hover:shadow-glow-cyan transition-all">
          <Icon icon={cat.icon} width={20} class="text-accent-light" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-ink-emphasis group-hover:text-accent-light transition-colors">{$t(cat.labelKey)}</h3>
          <p class="text-[11px] text-ink-muted mt-1 leading-snug">{cat.desc}</p>
        </div>
        <div class="flex items-center gap-1 text-[10px] text-accent/70 group-hover:text-accent-light transition-colors mt-auto">
          <span>{$t('web.wiki.home_browse')}</span>
          <Icon icon="lucide:arrow-right" width={12} />
        </div>
      </a>
    {/each}
  </div>
</div>
