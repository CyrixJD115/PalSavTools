<script lang="ts">
  // Pal editor modal — full per-instance editing. Mirrors PlayerDetailModal's
  // structure (onMount load, doAction helper, optimistic reload, onupdated).
  // Sections: identity, level/rank, talents/IVs, souls, skills, work suitability,
  // vitals, and a footer with quick actions (Max Out, Heal, Learn All, Move,
  // Delete). All edits send PalEditRequest; HP is recomputed server-side.
  import { onMount } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import { t } from '$stores/index';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import SkillPicker from './SkillPicker.svelte';
  import MovePalDialog from './MovePalDialog.svelte';
  import type { PalDetail, PalEditRequest, SkillCatalogEntry } from '$types/index';

  let {
    instanceId,
    displayName,
    onclose,
    onupdated,
  }: {
    instanceId: string;
    displayName?: string;
    onclose: () => void;
    onupdated: () => void;
  } = $props();

  let pal = $state<PalDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let cheatMode = $state(false);
  let catalog = $state<{ passives: SkillCatalogEntry[]; actives: SkillCatalogEntry[] }>({ passives: [], actives: [] });
  let showMove = $state(false);

  // Editable local copies (synced from `pal` on load)
  let nickname = $state('');
  let level = $state(1);
  let rank = $state(1);
  let talentHp = $state(0);
  let talentShot = $state(0);
  let talentDefense = $state(0);
  let rankHp = $state(0);
  let rankAttack = $state(0);
  let rankDefense = $state(0);
  let rankCraft = $state(0);
  let passiveSkills = $state<string[]>([]);
  let activeSkills = $state<string[]>([]);
  let workMap = $state<Record<string, number>>({});
  let friendship = $state(0);
  let stomach = $state(0);
  let sanity = $state(100);

  async function load() {
    loading = true;
    error = null;
    try {
      const res = await api.palDetail(instanceId);
      pal = res.pal;
      syncFromPal();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadCatalog() {
    try {
      catalog = await api.palSkillCatalog();
    } catch { /* optional */ }
  }

  function syncFromPal() {
    if (!pal) return;
    nickname = pal.nickname ?? '';
    level = pal.level;
    rank = pal.rank;
    talentHp = pal.talent_hp;
    talentShot = pal.talent_shot;
    talentDefense = pal.talent_defense;
    rankHp = pal.rank_hp;
    rankAttack = pal.rank_attack;
    rankDefense = pal.rank_defense;
    rankCraft = pal.rank_craftspeed;
    passiveSkills = [...pal.passive_skills];
    activeSkills = [...pal.active_skills];
    workMap = { ...pal.work_suitability };
    friendship = pal.friendship_point;
    stomach = pal.stomach;
    sanity = pal.sanity;
  }

  onMount(() => {
    load();
    loadCatalog();
  });

  async function save() {
    if (!pal) return;
    actionError = null;
    actionLoading = 'save';
    try {
      const body: PalEditRequest = {
        nickname,
        level,
        rank,
        talent_hp: talentHp,
        talent_shot: talentShot,
        talent_defense: talentDefense,
        rank_hp: rankHp,
        rank_attack: rankAttack,
        rank_defense: rankDefense,
        rank_craftspeed: rankCraft,
        passive_skills: passiveSkills,
        active_skills: activeSkills,
        work_suitability: workMap,
        friendship_point: friendship,
        cheat_mode: cheatMode,
      };
      const res = await api.editPal(instanceId, body);
      pal = res.pal;
      syncFromPal();
      onupdated();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function doAction(name: string, fn: () => Promise<{ pal: PalDetail }>) {
    actionError = null;
    actionLoading = name;
    try {
      const res = await fn();
      pal = res.pal;
      syncFromPal();
      onupdated();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function maxOut() {
    await doAction('max-out', () => api.maxOutPal(instanceId, cheatMode));
  }
  async function heal() {
    await doAction('heal', () => api.healPal(instanceId));
  }
  async function learnAll() {
    await doAction('learn-all', () => api.learnAllPal(instanceId, cheatMode));
  }
  async function toggleGender() {
    if (!pal) return;
    const next = pal.gender === 'Male' ? 'Female' : 'Male';
    await doAction('gender', async () => {
      await api.editPal(instanceId, { gender: next });
      return await api.palDetail(instanceId);
    });
  }
  async function toggleLucky() {
    if (!pal) return;
    await doAction('lucky', async () => {
      await api.editPal(instanceId, { is_lucky: !pal!.is_lucky });
      return await api.palDetail(instanceId);
    });
  }
  async function toggleBoss() {
    if (!pal || !pal.boss_available) return;
    await doAction('boss', async () => {
      await api.editPal(instanceId, { is_boss: !pal!.is_boss });
      return await api.palDetail(instanceId);
    });
  }
  async function doDelete() {
    if (!confirm($t('web.pal_editor.confirm_delete'))) return;
    actionError = null;
    actionLoading = 'delete';
    try {
      await api.deletePal(instanceId);
      onupdated();
      onclose();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  const cap = $derived(cheatMode ? 255 : 100);
  const soulCap = $derived(cheatMode ? 255 : 20);
  const levelCap = $derived(cheatMode ? 255 : 80);
  const rankCap = $derived(cheatMode ? 255 : 5);
  const passiveSlotCap = $derived(cheatMode ? 99 : 4);

  const WORK_KEYS: [string, string][] = [
    ['EmitFlame', 'Kindling'], ['Watering', 'Watering'], ['Seeding', 'Seeding'],
    ['GenerateElectricity', 'Electricity'], ['Handcraft', 'Handiwork'],
    ['Collection', 'Harvesting'], ['Deforest', 'Lumbering'], ['Mining', 'Mining'],
    ['OilExtraction', 'Oil'], ['ProductMedicine', 'Medicine'], ['Cool', 'Cooling'],
    ['Transport', 'Transport'], ['MonsterFarm', 'Farming'],
  ];

  function setWork(key: string, val: number) {
    workMap = { ...workMap, [key]: Math.max(0, Math.min(10, val)) };
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} role="dialog" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" transition:fade={{ duration: 150 }}></div>
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-2xl w-full mx-4 max-h-[88vh] overflow-y-auto animate-scale-in"
    transition:scale={{ start: 0.95, duration: 150 }}
    role="presentation"
    onclick={(e: MouseEvent) => e.stopPropagation()}
  >
    <!-- header -->
    <div class="sticky top-0 z-10 bg-bg-surface/95 backdrop-blur flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-3 min-w-0">
        {#if pal?.icon}
          <img src={assetUrl(pal.icon)} alt={pal.display_name ?? ''} class="w-10 h-10 object-contain rounded-4 bg-bg-deep" onerror={imgOnError} />
        {/if}
        <div class="min-w-0">
          <h2 class="text-lg font-bold heading-gradient truncate">{pal?.display_name ?? displayName}</h2>
          <p class="text-[11px] text-ink-muted font-mono truncate">{pal?.character_id}</p>
        </div>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button
          class="px-2 py-1 rounded-4 text-[10px] font-medium transition-fast {cheatMode ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' : 'bg-bg-elevated text-ink-muted border border-line/40'}"
          onclick={() => (cheatMode = !cheatMode)}
          title="Cheat mode raises caps to 255"
        >🐛</button>
        <button class="text-ink-muted hover:text-ink-primary transition-fast" onclick={onclose}>
          <Icon icon="lucide:x" width={20} />
        </button>
      </div>
    </div>

    {#if loading}
      <div class="flex justify-center py-16"><Spinner /></div>
    {:else if error}
      <p class="text-sm text-rose-400 p-6">{error}</p>
    {:else if pal}
      <div class="p-4 space-y-5">
        <!-- identity row -->
        <div class="flex flex-wrap items-center gap-2">
          <input bind:value={nickname} placeholder="Nickname" class="input text-sm flex-1 min-w-40" />
          <button class="px-2 py-1.5 rounded-4 text-xs border border-line/40 bg-bg-elevated hover:bg-bg-hover transition-fast {pal.gender === 'Female' ? 'text-pink-400' : 'text-sky-400'}" onclick={toggleGender} title="Toggle gender">
            <Icon icon={pal.gender === 'Female' ? 'lucide:venus' : 'lucide:mars'} width={14} />
          </button>
          {#if pal.boss_available}
            <button class="px-2 py-1.5 rounded-4 text-xs border transition-fast {pal.is_boss ? 'bg-amber-500/20 text-amber-400 border-amber-500/40' : 'border-line/40 bg-bg-elevated text-ink-muted'}" onclick={toggleBoss} title="Toggle boss">BOSS</button>
          {/if}
          <button class="px-2 py-1.5 rounded-4 text-xs border transition-fast {pal.is_lucky ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40' : 'border-line/40 bg-bg-elevated text-ink-muted'}" onclick={toggleLucky} title="Toggle lucky">★</button>
          {#if pal.is_sick}<Badge tone="error">{$t('web.pal_editor.sick')}</Badge>{/if}
          {#if pal.is_predator}<Badge tone="error">Predator</Badge>{/if}
        </div>

        <!-- level + rank -->
        <div class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.pal_editor.level')} (1-{levelCap})</span>
            <input type="number" min="1" max={levelCap} bind:value={level} class="input text-sm w-full" />
          </label>
          <label class="block">
            <span class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.pal_editor.condenser_rank')} (1-{rankCap})</span>
            <input type="number" min="1" max={rankCap} bind:value={rank} class="input text-sm w-full" />
          </label>
        </div>

        <!-- talents / IVs -->
        <div>
          <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.pal_editor.ivs')} (0-{cap})</h3>
          <div class="grid grid-cols-3 gap-2">
            <label class="block"><span class="text-[10px] text-ink-muted">HP</span><input type="number" min="0" max={cap} bind:value={talentHp} class="input text-sm w-full" /></label>
            <label class="block"><span class="text-[10px] text-ink-muted">ATK</span><input type="number" min="0" max={cap} bind:value={talentShot} class="input text-sm w-full" /></label>
            <label class="block"><span class="text-[10px] text-ink-muted">DEF</span><input type="number" min="0" max={cap} bind:value={talentDefense} class="input text-sm w-full" /></label>
          </div>
        </div>

        <!-- souls -->
        <div>
          <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.pal_editor.souls')} (0-{soulCap})</h3>
          <div class="grid grid-cols-4 gap-2">
            <label class="block"><span class="text-[10px] text-ink-muted">HP</span><input type="number" min="0" max={soulCap} bind:value={rankHp} class="input text-sm w-full" /></label>
            <label class="block"><span class="text-[10px] text-ink-muted">ATK</span><input type="number" min="0" max={soulCap} bind:value={rankAttack} class="input text-sm w-full" /></label>
            <label class="block"><span class="text-[10px] text-ink-muted">DEF</span><input type="number" min="0" max={soulCap} bind:value={rankDefense} class="input text-sm w-full" /></label>
            <label class="block"><span class="text-[10px] text-ink-muted">Craft</span><input type="number" min="0" max={soulCap} bind:value={rankCraft} class="input text-sm w-full" /></label>
          </div>
        </div>

        <!-- skills -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider">{$t('web.pal_editor.passives')} ({passiveSkills.length}{#if !cheatMode}/{passiveSlotCap}{/if})</h3>
            <button class="text-[10px] text-accent hover:underline" onclick={learnAll} disabled={actionLoading === 'learn-all'}>
              {$t('web.pal_editor.learn_all_skills')}
            </button>
          </div>
          <SkillPicker
            catalog={catalog.passives}
            selected={passiveSkills}
            slotCap={passiveSlotCap}
            onselect={(asset) => (passiveSkills = [...passiveSkills, asset])}
            onremove={(asset) => (passiveSkills = passiveSkills.filter((s) => s !== asset))}
          />
        </div>

        <div>
          <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.pal_editor.active_skills')}</h3>
          <SkillPicker
            catalog={catalog.actives}
            selected={activeSkills}
            slotCap={cheatMode ? 99 : 3}
            prefix="EPalWazaID::"
            onselect={(asset) => (activeSkills = [...activeSkills, asset])}
            onremove={(asset) => (activeSkills = activeSkills.filter((s) => s !== asset && s !== `EPalWazaID::${asset}`))}
          />
        </div>

        <!-- work suitability -->
        <div>
          <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.pal_editor.work_suitability')} (0-10)</h3>
          <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {#each WORK_KEYS as [key, label]}
              <label class="block">
                <span class="text-[10px] text-ink-muted truncate block">{label}</span>
                <input
                  type="number" min="0" max="10"
                  value={workMap[key] ?? 0}
                  oninput={(e) => setWork(key, +(e.currentTarget as HTMLInputElement).value)}
                  class="input text-sm w-full"
                />
              </label>
            {/each}
          </div>
        </div>

        <!-- vitals -->
        <div>
          <h3 class="text-[10px] font-semibold text-ink-dim uppercase tracking-wider mb-2">{$t('web.pal_editor.vitals')}</h3>
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="flex justify-between bg-bg-elevated rounded-4 px-3 py-1.5"><span class="text-ink-muted">HP</span><span class="font-mono text-ink-primary">{Math.round((pal.hp || 0) / 1000)} / {Math.round((pal.max_hp || 0) / 1000)}</span></div>
            <label class="flex justify-between items-center bg-bg-elevated rounded-4 px-3 py-1.5"><span class="text-ink-muted">{$t('web.pal_editor.sanity')}</span><input type="number" min="0" max="100" bind:value={sanity} class="w-16 bg-transparent text-right font-mono text-ink-primary outline-none" /></label>
            <label class="flex justify-between items-center bg-bg-elevated rounded-4 px-3 py-1.5"><span class="text-ink-muted">{$t('web.pal_editor.stomach')}</span><input type="number" min="0" step="0.1" bind:value={stomach} class="w-16 bg-transparent text-right font-mono text-ink-primary outline-none" /></label>
            <label class="flex justify-between items-center bg-bg-elevated rounded-4 px-3 py-1.5"><span class="text-ink-muted">{$t('web.pal_editor.friendship')}</span><input type="number" min="0" bind:value={friendship} class="w-20 bg-transparent text-right font-mono text-ink-primary outline-none" /></label>
          </div>
        </div>

        {#if actionError}<p class="text-xs text-rose-400">{actionError}</p>{/if}

        <!-- footer actions -->
        <div class="flex flex-wrap gap-2 pt-2 border-t border-line/20">
          <button class="btn btn-primary text-xs" onclick={save} disabled={actionLoading === 'save'}>
            {#if actionLoading === 'save'}<Spinner size={14} />{:else}<Icon icon="lucide:save" width={13} />{/if}
            {$t('web.pal_editor.save')}
          </button>
          <button class="btn text-xs" onclick={maxOut} disabled={actionLoading === 'max-out'} title="Max all stats">
            <Icon icon="lucide:chevrons-up" width={13} /> {$t('web.pal_editor.max_out')}
          </button>
          <button class="btn text-xs" onclick={heal} disabled={actionLoading === 'heal'} title="Full heal">
            <Icon icon="lucide:heart-pulse" width={13} /> {$t('web.pal_editor.heal')}
          </button>
          <button class="btn text-xs" onclick={() => (showMove = true)} title="Move to party/palbox">
            <Icon icon="lucide:arrow-left-right" width={13} /> {$t('web.pal_editor.move')}
          </button>
          <button class="btn text-xs text-rose-400 hover:bg-rose-500/10 ml-auto" onclick={doDelete} disabled={actionLoading === 'delete'}>
            <Icon icon="lucide:trash-2" width={13} /> {$t('web.pal_editor.delete')}
          </button>
        </div>
      </div>
    {/if}

    {#if showMove && pal}
      <MovePalDialog
        instanceId={instanceId}
        ownerId={pal.owner_uid}
        onclose={() => (showMove = false)}
        onmoved={() => { showMove = false; load(); onupdated(); }}
      />
    {/if}
  </div>
</div>
