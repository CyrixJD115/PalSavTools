<script lang="ts">
  // Move-pal sub-dialog. Lists the owning player's Party and Palbox containers
  // as move targets. The container IDs come from the player's save data
  // (OtomoCharacterContainerId = party, PalStorageContainerId = palbox); we read
  // them via GET /players/{uid} which carries them on the detail.
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import type { PlayerDetail } from '$types/index';

  let {
    instanceId,
    ownerId,
    onclose,
    onmoved,
  }: {
    instanceId: string;
    ownerId: string | null;
    onclose: () => void;
    onmoved: () => void;
  } = $props();

  let player = $state<PlayerDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let moving = $state(false);
  // PlayerDetail may expose container ids; if not, the user pastes one.
  let partyId = $state('');
  let palboxId = $state('');

  onMount(async () => {
    if (!ownerId) {
      loading = false;
      return;
    }
    try {
      player = await api.playerDetail(ownerId);
      // Container ids aren't on the summary; if the detail lacks them, the
      // fields stay editable for manual entry.
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  async function move(targetId: string) {
    if (!targetId.trim()) return;
    moving = true;
    error = null;
    try {
      await api.movePal(instanceId, { target_container_id: targetId.trim(), player_uid: ownerId ?? '' });
      onmoved();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      moving = false;
    }
  }
</script>

<div class="border border-line/40 rounded-4 p-4 bg-bg-elevated space-y-3" transition:fade={{ duration: 120 }}>
  <div class="flex items-center justify-between">
    <h4 class="text-xs font-semibold text-ink-primary">{$t('web.pal_editor.move_title')}</h4>
    <button class="text-ink-muted hover:text-ink-primary" onclick={onclose}><Icon icon="lucide:x" width={14} /></button>
  </div>

  {#if loading}
    <div class="flex justify-center py-4"><Spinner /></div>
  {:else}
    {#if error}<p class="text-xs text-rose-400">{error}</p>{/if}
    <p class="text-[11px] text-ink-dim">{$t('web.pal_editor.move_hint')}</p>

    <div class="grid grid-cols-2 gap-2">
      <div>
        <span class="text-[10px] text-ink-muted block mb-1">{$t('web.pal_editor.party_id')}</span>
        <input bind:value={partyId} placeholder="OtomoCharacterContainerId" class="input text-[11px] font-mono" />
        <button class="btn btn-primary text-[11px] w-full mt-1" disabled={!partyId.trim() || moving} onclick={() => move(partyId)}>
          {$t('web.pal_editor.move_to_party')}
        </button>
      </div>
      <div>
        <span class="text-[10px] text-ink-muted block mb-1">{$t('web.pal_editor.palbox_id')}</span>
        <input bind:value={palboxId} placeholder="PalStorageContainerId" class="input text-[11px] font-mono" />
        <button class="btn btn-primary text-[11px] w-full mt-1" disabled={!palboxId.trim() || moving} onclick={() => move(palboxId)}>
          {$t('web.pal_editor.move_to_palbox')}
        </button>
      </div>
    </div>
  {/if}
</div>
