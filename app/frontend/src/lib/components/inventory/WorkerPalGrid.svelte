<script lang="ts">
  // Read-only grid of working pals deployed at a base camp. Reuses the pal
  // tile look (circular icon + level + passives pips) but without click-to-edit
  // — clicking is a no-op in v1 (a future iteration can deep-link to the
  // pal editor).
  import Icon from '@iconify/svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import { t } from '$stores/index';
  import type { PalSummary } from '$types/index';

  let { workers }: { workers: PalSummary[] } = $props();
</script>

<div class="space-y-2">
  <p class="text-[10px] font-semibold uppercase tracking-widest text-ink-dim flex items-center gap-1.5">
    <Icon icon="lucide:users" width={11} />
    {$t('web.base_inventory.workers', 'Working Pals')}
    {#if workers.length > 0}
      <span class="text-ink-muted normal-case tracking-normal">({workers.length})</span>
    {/if}
  </p>

  {#if workers.length === 0}
    <EmptyState icon="lucide:user-x">
      <p class="text-xs">{$t('web.base_inventory.no_workers', 'No working pals deployed at this base.')}</p>
    </EmptyState>
  {:else}
    <div class="grid grid-cols-4 sm:grid-cols-6 gap-2">
      {#each workers as pal (pal.instance_id)}
        <div class="flex flex-col items-center gap-1 group">
          <div class="relative">
            <div class="h-14 w-14 rounded-full outline outline-2 outline-offset-2 outline-line/50 bg-bg-deep overflow-hidden">
              <img
                src={assetUrl(pal.icon)}
                alt={pal.display_name ?? pal.character_id}
                class="h-14 w-14 rounded-full object-cover"
                onerror={imgOnError}
                loading="lazy"
              />
            </div>
            {#if pal.level}
              <span class="absolute -bottom-1 left-0 text-[10px] font-bold text-ink-primary bg-bg-deep/90 px-1 rounded-2">
                {pal.level}
              </span>
            {/if}
          </div>
          <p class="text-[10px] text-ink-secondary text-center leading-tight line-clamp-1 w-full">
            {pal.nickname ?? pal.display_name ?? pal.character_id}
          </p>
        </div>
      {/each}
    </div>
  {/if}
</div>
