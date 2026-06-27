<script lang="ts">
  import { onMount } from 'svelte';
  import { saveLoaded } from '$stores/index';
  import { api } from '$lib/api/client';
  import Card from '$components/ui/Card.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import { Sparkles, Search, Shield, Sword, Brain, Heart, Zap } from '@lucide/svelte';
  import type { PalSummary } from '$types/index';

  let pals: PalSummary[] = $state([]);
  let total = $state(0);
  let loading = $state(false);
  let search = $state('');

  const filtered = $derived(
    search
      ? pals.filter(p =>
          (p.display_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
          p.character_id.toLowerCase().includes(search.toLowerCase()) ||
          (p.nickname ?? '').toLowerCase().includes(search.toLowerCase())
        )
      : pals
  );

  onMount(() => load());

  async function load() {
    if (!$saveLoaded) return;
    loading = true;
    try {
      const res = await api.pals();
      pals = res.pals;
      total = res.total;
    } catch { /* ignore */ }
    finally { loading = false; }
  }
</script>

<div class="p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold heading-gradient">Pal Editor</h1>
      <p class="text-sm text-ink-muted mt-1">{total} pals found</p>
    </div>
    {#if total > 0}
      <div class="relative">
        <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          type="text" placeholder="Search pals..."
          bind:value={search}
          class="pl-9 pr-3 py-1.5 text-sm rounded-lg bg-bg-elevated border border-line/50 text-ink-primary placeholder:text-ink-muted focus:outline-none focus:border-accent w-64"
        />
      </div>
    {/if}
  </div>

  {#if !$saveLoaded}
    <EmptyState icon={Sparkles} title="No save loaded">
      Load a save to browse and edit pals.
    </EmptyState>
  {:else if loading}
    <div class="text-center text-ink-muted py-12">Loading pals...</div>
  {:else if filtered.length === 0}
    <EmptyState icon={Sparkles} title="No pals found">
      No pal entries in this save.
    </EmptyState>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {#each filtered as pal}
        <Card class="p-3 space-y-2">
          <div class="flex items-start justify-between">
            <div class="min-w-0">
              <p class="text-sm font-semibold text-ink-primary truncate">
                {pal.display_name ?? pal.character_id}
              </p>
              {#if pal.nickname}
                <p class="text-xs text-ink-muted truncate">"{pal.nickname}"</p>
              {/if}
            </div>
            <Badge>{pal.gender}</Badge>
          </div>
          <div class="flex items-center gap-3 text-xs text-ink-muted">
            <span class="flex items-center gap-1"><Zap size={12} />Lv.{pal.level}</span>
            <span class="flex items-center gap-1"><Shield size={12} />★{pal.rank}</span>
          </div>
          <div class="grid grid-cols-3 gap-1 text-xs">
            <span class="{pal.talent_hp >= 90 ? "text-status-success" : pal.talent_hp >= 70 ? "text-yellow-400" : "text-ink-muted"}">
              <Heart size={12} class="inline" /> {pal.talent_hp}
            </span>
            <span class="{pal.talent_shot >= 90 ? "text-status-success" : pal.talent_shot >= 70 ? "text-yellow-400" : "text-ink-muted"}">
              <Sword size={12} class="inline" /> {pal.talent_shot}
            </span>
            <span class="{pal.talent_defense >= 90 ? "text-status-success" : pal.talent_defense >= 70 ? "text-yellow-400" : "text-ink-muted"}">
              <Brain size={12} class="inline" /> {pal.talent_defense}
            </span>
          </div>
          {#if pal.passive_skills.length > 0}
            <div class="flex flex-wrap gap-1">
              {#each pal.passive_skills.slice(0, 4) as skill}
                <span class="text-xs px-1.5 py-0.5 rounded bg-bg-elevated text-ink-muted truncate max-w-32">{skill}</span>
              {/each}
            </div>
          {/if}
        </Card>
      {/each}
    </div>
  {/if}
</div>
