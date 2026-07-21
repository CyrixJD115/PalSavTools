<script lang="ts">
  // Party & Pal Box panel — the reusable content. Renders inline (in the
  // Inventory page's Pals tab) or wrapped by PartyPalboxModal.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import type { PalGroupedResponse } from '$types/index';

  let {
    uid,
    partyId,
    palboxId,
  }: {
    uid: string;
    partyId: string | null;
    palboxId: string | null;
  } = $props();

  let grouped = $state<PalGroupedResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(() => { void load(); });

  async function load() {
    loading = true; error = null;
    try {
      grouped = await api.palGrouped(uid);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function palName(pal: NonNullable<PalGroupedResponse['party'][0]>): string {
    return pal.nickname ?? pal.display_name ?? pal.character_id;
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else if !grouped || (grouped.party.length === 0 && grouped.palbox.length === 0 && grouped.ungrouped.length === 0)}
  <EmptyState icon="lucide:paw-print" title={$t('web.inventory.no_pals', 'No pals here')} class="py-8" />
{:else}
  <div class="p-4 space-y-6">
    <!-- Party -->
    <div>
      <div class="flex items-center gap-2 mb-3">
        <h3 class="text-sm font-semibold text-ink-emphasis flex items-center gap-1.5">
          <Icon icon="lucide:star" width={14} class="text-accent" />
          {$t('web.inventory.tab_party', 'Party')}
        </h3>
        <Badge tone="accent">{grouped.party.length}</Badge>
        {#if partyId}
          <code class="text-[9px] font-mono text-ink-dim truncate ml-2">ID: {partyId.slice(0, 18)}…</code>
        {/if}
      </div>
      {#if grouped.party.length === 0}
        <p class="text-xs text-ink-dim italic">{$t('web.inventory.party_empty', 'No active pals in party.')}</p>
      {:else}
        <div class="flex flex-wrap gap-3">
          {#each grouped.party as pal (pal.instance_id)}
            <div class="flex flex-col items-center gap-1 group">
              <div class="h-14 w-14 rounded-full outline outline-2 outline-offset-2 outline-line/50 bg-bg-deep overflow-hidden group-hover:outline-accent/60 transition-fast">
                <img
                  src={assetUrl(pal.icon)}
                  alt={palName(pal)}
                  class="h-14 w-14 rounded-full object-cover"
                  onerror={imgOnError}
                  loading="lazy"
                />
              </div>
              <div class="text-center max-w-[4rem]">
                <p class="text-[10px] text-ink-secondary leading-tight truncate">{palName(pal)}</p>
                <p class="text-[9px] text-ink-dim tabular-nums">Lv.{pal.level}</p>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Pal Box -->
    <div>
      <div class="flex items-center gap-2 mb-3">
        <h3 class="text-sm font-semibold text-ink-emphasis flex items-center gap-1.5">
          <Icon icon="lucide:grid-3x3" width={14} class="text-accent-cyan" />
          {$t('web.inventory.tab_palbox', 'Pal Box')}
        </h3>
        <Badge tone="accent">{grouped.palbox.length}</Badge>
        {#if palboxId}
          <code class="text-[9px] font-mono text-ink-dim truncate ml-2">ID: {palboxId.slice(0, 18)}…</code>
        {/if}
      </div>
      {#if grouped.palbox.length === 0}
        <p class="text-xs text-ink-dim italic">{$t('web.inventory.palbox_empty', 'No pals in the palbox.')}</p>
      {:else}
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {#each grouped.palbox as pal (pal.instance_id)}
            <div class="flex items-center gap-2 p-2 rounded-4 bg-bg-deep/50 border border-line/30 hover:bg-bg-hover/40 transition-fast">
              <div class="h-10 w-10 rounded-full outline outline-2 outline-offset-1 outline-line/50 bg-bg-deep overflow-hidden shrink-0">
                <img
                  src={assetUrl(pal.icon)}
                  alt={palName(pal)}
                  class="h-10 w-10 rounded-full object-cover"
                  onerror={imgOnError}
                  loading="lazy"
                />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-[11px] text-ink-secondary leading-tight truncate">{palName(pal)}</p>
                <p class="text-[9px] text-ink-muted tabular-nums leading-tight">
                  Lv.{pal.level} · {pal.gender === 'Female' ? '♀' : pal.gender === 'Male' ? '♂' : '—'}
                  {#if pal.is_boss}· α{/if}
                  {#if pal.is_lucky}· ★{/if}
                </p>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Ungrouped -->
    {#if grouped.ungrouped.length > 0}
      <details class="text-xs text-ink-muted">
        <summary class="cursor-pointer font-medium">
          {$t('web.inventory.palbox_ungrouped', 'Other pals')} ({grouped.ungrouped.length})
        </summary>
        <div class="flex flex-wrap gap-1.5 mt-2">
          {#each grouped.ungrouped as pal (pal.instance_id)}
            <span class="px-1.5 py-0.5 rounded-2 bg-bg-deep/40 border border-line/30 text-[10px] text-ink-dim truncate max-w-28">
              {palName(pal)}
            </span>
          {/each}
        </div>
      </details>
    {/if}

    <!-- Open pal editor -->
    <div class="pt-2 border-t border-line/20">
      <a href="/pal-editor" class="btn btn-primary text-xs">
        <Icon icon="lucide:external-link" width={12} class="mr-1" />
        {$t('web.inventory.open_pal_editor', 'Open Pal Editor')}
      </a>
    </div>
  </div>
{/if}
