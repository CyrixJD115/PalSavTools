<script lang="ts">
  // Preset manager drawer — list/create/apply/delete presets. "Apply to
  // filtered pals" sends the current pal-editor grid's instance IDs to
  // POST /pals/apply-preset. Presets persist as JSON files server-side.
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import Spinner from '$components/ui/Spinner.svelte';
  import type { PalPreset } from '$types/index';

  let {
    onclose,
    onapplied,
    palIds,
  }: {
    onclose: () => void;
    onapplied: () => void;
    palIds: string[];
  } = $props();

  let presets = $state<PalPreset[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let creating = $state(false);
  let newName = $state('');
  // New-preset fields (all optional; unchecked = null = "don't touch")
  let newFields = $state<Record<string, unknown>>({});

  onMount(load);

  async function load() {
    loading = true;
    error = null;
    try {
      const res = await api.listPresets();
      presets = res.presets;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function create() {
    if (!newName.trim()) return;
    error = null;
    try {
      // Build the preset from checked fields only.
      const preset: PalPreset = { name: newName.trim(), ...newFields };
      await api.savePreset({ name: newName.trim(), preset });
      newName = '';
      newFields = {};
      creating = false;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function apply(preset: PalPreset) {
    if (!preset.id || palIds.length === 0) return;
    if (!confirm($t('web.pal_editor.preset_confirm', { count: palIds.length, name: preset.name }))) return;
    error = null;
    try {
      const res = await api.applyPreset({ instance_ids: palIds, preset_id: preset.id });
      const msg = $t('web.pal_editor.preset_applied', { applied: res.applied, failed: res.failed.length });
      if (res.failed.length) error = msg;
      onapplied();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function remove(preset: PalPreset) {
    if (!preset.id) return;
    if (!confirm($t('web.pal_editor.preset_delete_confirm', { name: preset.name }))) return;
    try {
      await api.deletePreset(preset.id);
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  // Quick-fill helpers for the create form
  const PRESET_FIELDS: [string, number][] = [
    ['talent_hp', 100], ['talent_shot', 100], ['talent_defense', 100],
    ['rank_hp', 20], ['rank_attack', 20], ['rank_defense', 20], ['rank_craftspeed', 20],
    ['rank', 5], ['level', 80],
  ];
  function toggle(key: string, value: unknown) {
    newFields = { ...newFields, [key]: newFields[key] === undefined ? value : undefined };
  }
  const isChecked = (key: string) => newFields[key] !== undefined;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex justify-end" onclick={onclose} role="dialog" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" transition:fade={{ duration: 150 }}></div>
  <div
    class="relative bg-bg-surface border-l border-line/40 w-full max-w-md h-full overflow-y-auto shadow-xl"
    transition:fly={{ x: 400, duration: 200 }}
    role="presentation"
    onclick={(e: MouseEvent) => e.stopPropagation()}
  >
    <!-- header -->
    <div class="sticky top-0 bg-bg-surface/95 backdrop-blur flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:layers" width={18} class="text-accent" />
        <h2 class="text-base font-bold heading-gradient">{$t('web.pal_editor.presets_title')}</h2>
      </div>
      <button class="text-ink-muted hover:text-ink-primary" onclick={onclose}><Icon icon="lucide:x" width={18} /></button>
    </div>

    <div class="p-4 space-y-4">
      {#if error}<p class="text-xs text-rose-400">{error}</p>{/if}

      {#if loading}
        <div class="flex justify-center py-8"><Spinner /></div>
      {:else}
        <!-- existing presets -->
        {#if presets.length === 0 && !creating}
          <p class="text-xs text-ink-dim text-center py-6">{$t('web.pal_editor.no_presets')}</p>
        {/if}
        {#each presets as preset (preset.id ?? preset.name)}
          <div class="border border-line/40 rounded-4 p-3 bg-bg-elevated/50 space-y-2">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-medium text-ink-primary truncate">{preset.name}</span>
              <div class="flex gap-1 shrink-0">
                <button class="btn btn-primary text-[11px] px-2 py-1" onclick={() => apply(preset)} disabled={palIds.length === 0}>
                  {$t('web.pal_editor.apply')}
                </button>
                <button class="text-ink-dim hover:text-rose-400 p-1" onclick={() => remove(preset)} title={$t('web.pal_editor.delete')}>
                  <Icon icon="lucide:trash-2" width={13} />
                </button>
              </div>
            </div>
            <div class="flex flex-wrap gap-1">
              {#each Object.entries(preset) as [k, v]}
                {#if v !== null && v !== undefined && k !== 'id' && k !== 'name'}
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-bg-deep text-ink-muted">{k}={String(v).slice(0, 20)}</span>
                {/if}
              {/each}
            </div>
          </div>
        {/each}

        <!-- create new -->
        {#if creating}
          <div class="border border-accent/40 rounded-4 p-3 space-y-2 bg-bg-elevated/30">
            <input bind:value={newName} placeholder={$t('web.pal_editor.preset_name')} class="input text-sm" />
            <p class="text-[10px] text-ink-dim">{$t('web.pal_editor.preset_fields_hint')}</p>
            <div class="grid grid-cols-2 gap-1.5 text-[11px]">
              {#each PRESET_FIELDS as [key, val]}
                <label class="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={isChecked(key)} onchange={() => toggle(key, val)} class="accent-accent" />
                  <span class="text-ink-secondary">{key}={val}</span>
                </label>
              {/each}
            </div>
            <div class="flex gap-2">
              <button class="btn btn-primary text-xs flex-1" onclick={create} disabled={!newName.trim()}>{$t('web.pal_editor.create')}</button>
              <button class="btn text-xs" onclick={() => (creating = false)}>{$t('web.pal_editor.cancel')}</button>
            </div>
          </div>
        {:else}
          <button class="btn text-xs w-full" onclick={() => (creating = true)}>
            <Icon icon="lucide:plus" width={13} /> {$t('web.pal_editor.new_preset')}
          </button>
        {/if}
      {/if}
    </div>
  </div>
</div>
