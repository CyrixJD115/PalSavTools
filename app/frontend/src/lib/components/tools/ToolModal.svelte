<script lang="ts">
  import { api } from '$lib/api/client';
  import type { ToolInfo } from '$types/index';
  import { saveSummary, saveLoaded, t } from '$stores/index';
  import { tick } from 'svelte';

  let { tool, open, onClose }: {
    tool: ToolInfo | null;
    open: boolean;
    onClose: () => void;
  } = $props();

  let running = $state(false);
  let result = $state<string | null>(null);
  let resultOk = $state(false);
  let error = $state<string | null>(null);

  // Form values
  let convertDirection = $state('sav2json');
  let convertInput = $state('');
  let convertOutput = $state('');

  let idsInput = $state('');

  let mapPath = $state('');

  let slotLevelPath = $state('');
  let slotPlayersPath = $state('');
  let slotCount = $state(960);
  let slotUseLoaded = $state(false);

  let fixLevelPath = $state('');
  let fixUseLoaded = $state(false);
  let fixSourceUid = $state('');
  let fixTargetUid = $state('');
  let fixGuildLevelPath = $state('');
  let fixGuildPlayerUid = $state('');
  let fixGuildTargetGuildId = $state('');
  let fixGuildUseLoaded = $state(false);

  let ctSourcePath = $state('');
  let ctTargetPath = $state('');
  let ctSourceUid = $state('');
  let ctTargetUid = $state('');

  let pmSourcePath = $state('');
  let pmTargetPath = $state('');
  let pmSourceUid = $state('');
  let pmTargetUid = $state('');

  let exportOutputPath = $state('');

  let overlayEl = $state<HTMLDivElement>();

  function resetForm(): void {
    convertDirection = 'sav2json';
    convertInput = '';
    convertOutput = '';
    idsInput = '';
    mapPath = '';
    slotCount = 960;
    // Pre-populate slot-injector paths from loaded save if available
    const summary = $saveSummary;
    if (summary) {
      slotLevelPath = summary.save_dir ? summary.save_dir + '/Level.sav' : '';
      slotPlayersPath = summary.players_dir ?? '';
      slotUseLoaded = true;
    } else {
      slotLevelPath = '';
      slotPlayersPath = '';
      slotUseLoaded = false;
    }
    fixLevelPath = summary ? (summary.save_dir + '/Level.sav') : '';
    fixUseLoaded = !!summary;
    fixSourceUid = '';
    fixTargetUid = '';
    fixGuildLevelPath = summary ? (summary.save_dir + '/Level.sav') : '';
    fixGuildPlayerUid = '';
    fixGuildTargetGuildId = '';
    fixGuildUseLoaded = !!summary;
    ctSourcePath = '';
    ctTargetPath = '';
    ctSourceUid = '';
    ctTargetUid = '';
    pmSourcePath = '';
    pmTargetPath = '';
    pmSourceUid = '';
    pmTargetUid = '';
    exportOutputPath = '';
    result = null;
    error = null;
    resultOk = false;
  }

  async function execute(): Promise<void> {
    if (!tool) return;
    running = true;
    result = null;
    resultOk = false;
    error = null;

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let res: any;
      switch (tool.id) {
        case 'convert':
          res = await api.toolConvert({
            direction: convertDirection,
            input_path: convertInput,
            output_path: convertOutput || undefined,
          });
          break;
        case 'convert-ids':
          res = await api.toolConvertIds({ input: idsInput });
          resultOk = true;
          result = `${$t('web.tools.result_steam_id')} ${(res as any).steam_id ?? '—'}\n${$t('web.tools.result_palworld_uid')} ${(res as any).palworld_uid ?? '—'}\n${$t('web.tools.result_nosteam_uid')} ${(res as any).nosteam_uid ?? '—'}`;
          return; // skip generic message
        case 'restore-map':
          res = await api.toolRestoreMap({ path: mapPath });
          break;
        case 'slot-injector':
          res = await api.toolSlotInject({
            level_sav_path: slotUseLoaded ? undefined : slotLevelPath,
            players_folder: slotPlayersPath || undefined,
            new_slot_count: slotCount,
            use_loaded_save: slotUseLoaded,
          });
          break;
        case 'fix-host-save':
          res = await api.toolFixHostSave({
            level_sav_path: fixUseLoaded ? undefined : fixLevelPath,
            old_uid: fixSourceUid,
            new_uid: fixTargetUid,
            use_loaded_save: fixUseLoaded,
          });
          break;
        case 'fix-guild':
          res = await api.toolFixGuild({
            level_sav_path: fixGuildUseLoaded ? undefined : fixGuildLevelPath,
            player_uid: fixGuildPlayerUid,
            target_guild_id: fixGuildTargetGuildId,
            use_loaded_save: fixGuildUseLoaded,
          });
          break;
        case 'character-transfer':
          res = await api.toolCharacterTransfer({
            source_sav_path: ctSourcePath,
            target_sav_path: ctTargetPath,
            source_player_uid: ctSourceUid,
            target_player_uid: ctTargetUid || undefined,
          });
          break;
        case 'player-migrate':
          res = await api.toolPlayerMigrate({
            source_sav_path: pmSourcePath,
            target_sav_path: pmTargetPath,
            source_player_uid: pmSourceUid,
            target_player_uid: pmTargetUid || undefined,
          });
          break;
        case 'convert-export':
          res = await api.toolConvertExport({
            output_path: exportOutputPath || undefined,
          });
          break;
        default:
          res = { success: false, message: $t('web.tools.not_available', { id: tool.id }) };
      }
      resultOk = res.success ?? false;
      result = res.details
        ? res.message + '\n' + JSON.stringify(res.details, null, 2)
        : res.message;
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
      resultOk = false;
    } finally {
      running = false;
    }
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && open) onClose();
  }

  $effect(() => {
    if (open) {
      resetForm();
      tick();
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
{#if open && tool}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    onclick={(e) => { if (e.target === overlayEl) onClose(); }}
    bind:this={overlayEl}
  >
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
    <div class="relative w-full max-w-lg mx-4 max-h-[85vh] flex flex-col rounded-xl bg-surface border-2 border-accent/30 shadow-2xl">
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
        <h2 class="text-base font-semibold text-ink-emphasis">{tool.name}</h2>
        <button onclick={onClose} class="btn-icon btn-icon-muted" aria-label={$t('web.common.close')}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <p class="text-sm text-ink-muted">{tool.description}</p>

        {#if tool.windows_only}
          <div class="rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-3 text-sm text-amber-300">
            {$t('web.tools.requires_windows')}
          </div>
        {:else if tool.id === 'convert'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_direction')}</span>
              <select bind:value={convertDirection} class="input w-full mt-1">
                <option value="sav2json">{$t('web.tools.field_sav2json')}</option>
                <option value="json2sav">{$t('web.tools.field_json2sav')}</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_input_path')}</span>
              <input type="text" bind:value={convertInput} class="input w-full mt-1" placeholder={$t('web.tools.ph_level_sav')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_output_path')}</span>
              <input type="text" bind:value={convertOutput} class="input w-full mt-1" placeholder={$t('web.tools.ph_auto_derived')} />
            </label>
          </div>
        {:else if tool.id === 'convert-ids'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_id_input')}</span>
              <input type="text" bind:value={idsInput} class="input w-full mt-1" placeholder={$t('web.tools.ph_steam_id')} />
            </label>
          </div>
        {:else if tool.id === 'restore-map'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_localdata_path')}</span>
              <input type="text" bind:value={mapPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_localdata')} />
            </label>
          </div>
        {:else if tool.id === 'slot-injector'}
          <div class="space-y-3">
            {#if $saveLoaded}
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={slotUseLoaded} class="checkbox" />
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_use_loaded')}</span>
              </label>
            {/if}
            {#if !slotUseLoaded || !$saveLoaded}
              <label class="block">
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_level_sav_path')}</span>
                <input type="text" bind:value={slotLevelPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_level_sav')} />
              </label>
              <label class="block">
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_players_folder')}</span>
                <input type="text" bind:value={slotPlayersPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_auto_detected')} />
              </label>
            {:else}
              <div class="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 text-xs text-ink-secondary">
                <div>{$t('web.tools.result_save')} <span class="text-ink-emphasis">{$saveSummary?.filename}</span></div>
                <div>{$t('web.tools.result_directory')} <span class="text-ink-emphasis truncate block">{$saveSummary?.save_dir}</span></div>
              </div>
            {/if}
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_new_slot_count')}</span>
              <input type="number" bind:value={slotCount} class="input w-full mt-1" min="1" max="960" />
            </label>
          </div>
        {:else if tool.id === 'fix-host-save'}
          <div class="space-y-3">
            {#if $saveLoaded}
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={fixUseLoaded} class="checkbox" />
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_use_loaded')}</span>
              </label>
            {/if}
            {#if !fixUseLoaded || !$saveLoaded}
              <label class="block">
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_level_sav_path')}</span>
                <input type="text" bind:value={fixLevelPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_level_sav')} />
              </label>
            {:else}
              <div class="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 text-xs text-ink-secondary">
                <div>{$t('web.tools.result_save')} <span class="text-ink-emphasis">{$saveSummary?.filename}</span></div>
                <div>{$t('web.tools.result_directory')} <span class="text-ink-emphasis truncate block">{$saveSummary?.save_dir}</span></div>
              </div>
            {/if}
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_source_uid')}</span>
              <input type="text" bind:value={fixSourceUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_migrate_from')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_uid')}</span>
              <input type="text" bind:value={fixTargetUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_migrate_to')} />
            </label>
          </div>
        {:else if tool.id === 'fix-guild'}
          <div class="space-y-3">
            {#if $saveLoaded}
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={fixGuildUseLoaded} class="checkbox" />
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_use_loaded')}</span>
              </label>
            {/if}
            {#if !fixGuildUseLoaded || !$saveLoaded}
              <label class="block">
                <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_level_sav_path')}</span>
                <input type="text" bind:value={fixGuildLevelPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_level_sav')} />
              </label>
            {:else}
              <div class="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 text-xs text-ink-secondary">
                <div>{$t('web.tools.result_save')} <span class="text-ink-emphasis">{$saveSummary?.filename}</span></div>
                <div>{$t('web.tools.result_directory')} <span class="text-ink-emphasis truncate block">{$saveSummary?.save_dir}</span></div>
              </div>
            {/if}
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_player_uid')}</span>
              <input type="text" bind:value={fixGuildPlayerUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_player_move')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_guild')}</span>
              <input type="text" bind:value={fixGuildTargetGuildId} class="input w-full mt-1" placeholder={$t('web.tools.ph_guild_move')} />
            </label>
          </div>
        {:else if tool.id === 'character-transfer'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_source_level')}</span>
              <input type="text" bind:value={ctSourcePath} class="input w-full mt-1" placeholder={$t('web.tools.ph_source_level')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_level')}</span>
              <input type="text" bind:value={ctTargetPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_target_level')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_source_uid')}</span>
              <input type="text" bind:value={ctSourceUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_transfer_from')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_uid_optional')}</span>
              <input type="text" bind:value={ctTargetUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_use_source')} />
            </label>
          </div>
        {:else if tool.id === 'player-migrate'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_source_level')}</span>
              <input type="text" bind:value={pmSourcePath} class="input w-full mt-1" placeholder={$t('web.tools.ph_source_level')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_level')}</span>
              <input type="text" bind:value={pmTargetPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_target_level')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_source_uid')}</span>
              <input type="text" bind:value={pmSourceUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_migrate_uid')} />
            </label>
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_target_uid_optional')}</span>
              <input type="text" bind:value={pmTargetUid} class="input w-full mt-1" placeholder={$t('web.tools.ph_use_source')} />
            </label>
          </div>
        {:else if tool.id === 'convert-export'}
          <div class="space-y-3">
            <label class="block">
              <span class="text-xs font-medium text-ink-secondary">{$t('web.tools.field_output_path')}</span>
              <input type="text" bind:value={exportOutputPath} class="input w-full mt-1" placeholder={$t('web.tools.ph_auto_from_loaded')} />
            </label>
            {#if $saveLoaded}
              <div class="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 text-xs text-ink-secondary">
                <div>{$t('web.tools.result_save')} <span class="text-ink-emphasis">{$saveSummary?.filename}</span></div>
                <div>{$t('web.tools.result_export_to')} <span class="text-ink-emphasis truncate block">{exportOutputPath || ($saveSummary?.save_dir + '/' + ($saveSummary?.filename ?? 'Level') + '.json')}</span></div>
              </div>
            {/if}
          </div>
        {:else if tool.id === 'backup'}
          <div class="rounded-lg bg-accent/10 border border-accent/20 px-4 py-3 text-sm text-ink-secondary">
            {$t('web.tools.create_backup_desc')}
          </div>
        {:else}
          <div class="rounded-lg bg-ink-dim/10 px-4 py-3 text-sm text-ink-muted">
            {$t('web.tools.not_implemented')}
          </div>
        {/if}

        <!-- Result output -->
        {#if result}
          <div class="rounded-lg {resultOk ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'} px-4 py-3">
            <pre class="text-xs whitespace-pre-wrap font-mono {resultOk ? 'text-emerald-300' : 'text-red-300'}">{result}</pre>
          </div>
        {/if}
        {#if error}
          <div class="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 px-5 py-4 border-t border-line shrink-0">
        {#if !tool.windows_only && tool.id !== 'backup'}
          <button
            onclick={execute}
            disabled={running}
            class="btn btn-primary"
          >
            {#if running}
              <svg class="animate-spin -ml-1 mr-2 h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {$t('web.common.running')}
            {:else}
              {$t('web.common.execute')}
            {/if}
          </button>
        {/if}
        <button onclick={onClose} class="btn btn-ghost">{$t('web.common.close')}</button>
      </div>
    </div>
  </div>
{/if}
