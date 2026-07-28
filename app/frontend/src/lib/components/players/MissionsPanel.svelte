<script lang="ts">
  // Missions / quests bulk editor — reusable sub-tab panel.
  // Renders inline in the Player Editor's Missions tab. Self-loads the quest
  // catalog + the player's status on mount, and writes back via setPlayerQuests.
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import Spinner from '$components/ui/Spinner.svelte';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import type { QuestEntry } from '$types/index';

  let { uid }: { uid: string } = $props();

  let questEntries = $state<QuestEntry[]>([]);
  let supported = $state(true);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saving = $state(false);
  let questSearch = $state('');
  let selectedQuests = $state<Set<string>>(new Set());

  const QUEST_GROUP_ORDER = ['Main', 'Sub', 'Hidden', 'Other'] as const;

  onMount(() => { void load(); });

  async function load() {
    loading = true; error = null;
    try {
      const resp = await api.playerQuests(uid);
      questEntries = resp.quests;
      supported = resp.supported;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
    selectedQuests = new Set();
    questSearch = '';
  }

  const filteredQuests = $derived(
    questEntries.filter((q) => {
      const term = questSearch.trim().toLowerCase();
      if (!term) return true;
      return q.name.toLowerCase().includes(term) || q.id.toLowerCase().includes(term);
    }),
  );

  const questsByGroup = $derived.by(() => {
    const groups: Record<string, QuestEntry[]> = {};
    for (const q of filteredQuests) {
      const g = QUEST_GROUP_ORDER.includes(q.type as typeof QUEST_GROUP_ORDER[number])
        ? q.type : 'Other';
      (groups[g] ??= []).push(q);
    }
    return groups;
  });

  function toggleQuest(id: string) {
    const next = new Set(selectedQuests);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedQuests = next;
  }

  function toggleGroupAll(entries: QuestEntry[], checked: boolean) {
    const next = new Set(selectedQuests);
    for (const q of entries) {
      if (checked) next.add(q.id); else next.delete(q.id);
    }
    selectedQuests = next;
  }

  async function completeSelected() {
    const ids = [...selectedQuests];
    if (!ids.length) { toast.info($t('web.players.missions_none_selected', 'No missions selected.')); return; }
    saving = true;
    try {
      await api.setPlayerQuests(uid, { complete: ids });
      toast.success($t('web.players.missions_complete', 'Complete Selected'));
      const map = new Map(questEntries.map((q) => [q.id, q]));
      for (const id of ids) { const q = map.get(id); if (q) q.status = 'completed'; }
      questEntries = [...questEntries];
      selectedQuests = new Set();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      saving = false;
    }
  }

  async function resetSelected() {
    const ids = [...selectedQuests];
    if (!ids.length) { toast.info($t('web.players.missions_none_selected', 'No missions selected.')); return; }
    saving = true;
    try {
      await api.setPlayerQuests(uid, { reset: ids });
      toast.success($t('web.players.missions_reset', 'Reset Selected'));
      const map = new Map(questEntries.map((q) => [q.id, q]));
      for (const id of ids) {
        const q = map.get(id);
        if (q && q.status === 'completed') q.status = 'not_started';
      }
      questEntries = [...questEntries];
      selectedQuests = new Set();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      saving = false;
    }
  }
</script>

{#if loading}
  <div class="flex justify-center py-16"><Spinner size={24} /></div>
{:else if error}
  <p class="text-sm text-status-error p-4">{error}</p>
{:else}
  <div class="p-5 space-y-4 max-w-3xl mx-auto">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:scroll-text" width={16} class="text-accent" />
        <h3 class="text-sm font-semibold text-ink-emphasis">{$t('web.players.edit_missions', 'Missions')}</h3>
        {#if questEntries.length}
          <Badge tone="accent">{questEntries.length}</Badge>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        {#if selectedQuests.size > 0}
          <span class="text-[10px] text-ink-dim">{selectedQuests.size} selected</span>
        {/if}
      </div>
    </div>

    {#if !supported}
      <p class="text-xs text-status-warning">{$t('web.players.missions_unsupported')}</p>
    {/if}

    {#if questEntries.length === 0}
      <EmptyState icon="lucide:scroll-text" title={$t('web.players.edit_missions', 'Missions')} class="py-8">
        <p class="text-xs">{$t('web.players.missions_unsupported')}</p>
      </EmptyState>
    {:else}
      <!-- toolbar -->
      <div class="flex items-center gap-2 flex-wrap">
        <div class="relative flex-1 min-w-48">
          <Icon icon="lucide:search" width={12} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
          <input
            type="text"
            class="input text-xs pl-7 w-full"
            placeholder={$t('web.players.missions_search', 'Search missions...')}
            bind:value={questSearch}
            disabled={saving}
          />
        </div>
        <Button variant="primary" onclick={completeSelected} disabled={saving || !supported} class="!text-xs">
          <Icon icon="lucide:check-check" width={13} class="mr-1" />
          {$t('web.players.missions_complete', 'Complete Selected')}
        </Button>
        <Button variant="secondary" onclick={resetSelected} disabled={saving || !supported} class="!text-xs">
          <Icon icon="lucide:rotate-ccw" width={13} class="mr-1" />
          {$t('web.players.missions_reset', 'Reset Selected')}
        </Button>
      </div>

      <!-- grouped list -->
      <div class="border border-line/30 rounded-4 overflow-hidden">
        {#if filteredQuests.length === 0}
          <p class="text-xs text-ink-muted p-3">{$t('web.players.missions_no_results', 'No missions match your search.')}</p>
        {/if}
        {#each QUEST_GROUP_ORDER as groupKey (groupKey)}
          {@const entries = questsByGroup[groupKey] ?? []}
          {#if entries.length}
            <div class="flex items-center gap-2 px-3 py-2 bg-bg-deep/40 border-b border-line/20 sticky top-0">
              <input
                type="checkbox"
                checked={entries.every((q) => selectedQuests.has(q.id))}
                onchange={(e) => toggleGroupAll(entries, (e.target as HTMLInputElement).checked)}
                disabled={saving}
              />
              <span class="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                {$t(`web.players.missions_group_${groupKey.toLowerCase()}`)}
              </span>
              <Badge tone="neutral" class="!text-[9px]">{entries.length}</Badge>
            </div>
            {#each entries as q (q.id)}
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <div
                class="flex items-center gap-2 px-3 py-1.5 border-b border-line/10 last:border-b-0 hover:bg-bg-hover/40 cursor-pointer transition-fast {selectedQuests.has(q.id) ? 'bg-accent/5' : ''}"
                role="button"
                tabindex="0"
                onclick={() => toggleQuest(q.id)}
                onkeydown={(e) => e.key === 'Enter' && toggleQuest(q.id)}
              >
                <input type="checkbox" checked={selectedQuests.has(q.id)} disabled={saving} />
                <span class="flex-1 text-xs text-ink-primary truncate">{q.name}</span>
                {#if q.status === 'completed'}
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-status-success/20 text-status-success whitespace-nowrap">{$t('web.players.missions_status_completed')}</span>
                {:else if q.status === 'active'}
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-accent/20 text-accent whitespace-nowrap">{$t('web.players.missions_status_active')}</span>
                {:else}
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-ink-dim whitespace-nowrap">{$t('web.players.missions_status_not_started')}</span>
                {/if}
              </div>
            {/each}
          {/if}
        {/each}
      </div>
    {/if}
  </div>
{/if}
