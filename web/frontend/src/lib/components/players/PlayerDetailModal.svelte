<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import Icon from '@iconify/svelte';
  import { api } from '$lib/api/client';
  import type { PlayerDetail } from '$types/index';
  import Button from '$components/ui/Button.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Spinner from '$components/ui/Spinner.svelte';

  let { uid, name: playerName, onclose, onupdated }: {
    uid: string;
    name: string;
    onclose: () => void;
    onupdated: () => void;
  } = $props();

  let detail = $state<PlayerDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionLoading = $state<string | null>(null);
  let renameValue = $state('');
  let editingName = $state(false);
  let levelValue = $state(1);
  let editingLevel = $state(false);
  let techPoints = $state(0);
  let bossTechPoints = $state(0);
  let editingTech = $state(false);
  let stats = $state({ max_hp: 0, max_sp: 0, attack: 0, weight: 0, capture_rate: 0, work_speed: 0, unused_stat_points: 0 });
  let editingStats = $state(false);

  async function load() {
    loading = true; error = null;
    try { detail = await api.playerDetail(uid); }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }
  onMount(load);

  async function doAction(name: string, fn: () => Promise<unknown>) {
    actionError = null;
    actionLoading = name;
    try {
      await fn();
      if (name !== 'close') await load();
      if (name === 'delete') onupdated();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionLoading = null;
    }
  }

  async function doRename() {
    if (!renameValue.trim()) return;
    await doAction('rename', () => api.renamePlayer(uid, { name: renameValue.trim() }));
    editingName = false;
  }

  async function doSetLevel() {
    await doAction('set-level', () => api.setPlayerLevel(uid, { level: levelValue }));
    editingLevel = false;
  }

  async function doTechPoints() {
    await doAction('tech-points', () => api.setPlayerTechPoints(uid, { tech_points: techPoints, boss_tech_points: bossTechPoints }));
    editingTech = false;
  }

  async function doStats() {
    const body: Record<string, number> = {};
    if (stats.max_hp) body.max_hp = stats.max_hp;
    if (stats.max_sp) body.max_sp = stats.max_sp;
    if (stats.attack) body.attack = stats.attack;
    if (stats.weight) body.weight = stats.weight;
    if (stats.capture_rate) body.capture_rate = stats.capture_rate;
    if (stats.work_speed) body.work_speed = stats.work_speed;
    body.unused_stat_points = stats.unused_stat_points;
    await doAction('stats', () => api.setPlayerStats(uid, body));
    editingStats = false;
  }

  function startRename() { renameValue = detail?.name ?? ''; editingName = true; }

  function startLevel() { levelValue = detail?.level ?? 1; editingLevel = true; }

  function startTech() {
    techPoints = 0; bossTechPoints = 0;
    editingTech = true;
  }

  function startStats() {
    stats = { max_hp: 0, max_sp: 0, attack: 0, weight: 0, capture_rate: 0, work_speed: 0, unused_stat_points: 0 };
    editingStats = true;
  }

  function handleDelete() {
    if (!confirm(`Delete player "${detail?.name ?? uid}"? This cannot be undone.`)) return;
    doAction('delete', () => api.deletePlayer(uid));
  }

  function handleViewingCage() {
    doAction('viewing-cage', () => api.unlockViewingCage(uid));
  }

  function handleResetTimestamp() {
    doAction('reset-timestamp', () => api.resetPlayerTimestamp(uid));
  }

  function handleUnlockTechs() {
    doAction('unlock-techs', () => api.unlockPlayerTechnologies(uid));
  }

  function handleMaxAbilities() {
    doAction('max-abilities', () => api.maxPlayerAbilities({ uids: [uid] }));
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} role="dialog" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto animate-scale-in"
    transition:scale={{ start: 0.95, duration: 150 }}
    role="presentation"
    onclick={(e: MouseEvent) => e.stopPropagation()}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:user" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">{detail?.name ?? playerName}</h2>
        {#if detail?.is_leader}<Badge tone="accent">Leader</Badge>{/if}
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast" onclick={onclose}>
        <Icon icon="lucide:x" width={20} />
      </button>
    </div>

    {#if loading}
      <div class="flex justify-center py-12"><Spinner size={24} /></div>
    {:else if error}
      <p class="text-sm text-status-error p-4">{error}</p>
    {:else if detail}
      <!-- stats row -->
      <div class="grid grid-cols-2 gap-4 p-4 border-b border-line/20 text-sm">
        <div><span class="text-ink-muted">Level:</span> <span class="tabular-nums text-ink-primary font-medium">{detail.level}</span></div>
        <div><span class="text-ink-muted">Pals owned:</span> <span class="tabular-nums text-ink-primary font-medium">{detail.pal_count}</span></div>
        <div><span class="text-ink-muted">Guild:</span> <Badge tone="accent">{detail.guild_name ?? '—'}</Badge></div>
        <div><span class="text-ink-muted">Guild level:</span> <span class="tabular-nums">{detail.guild_level}</span></div>
        <div class="col-span-2"><span class="text-ink-muted">Last seen:</span> <span class="tabular-nums">{detail.last_seen_text ?? 'Unknown'}</span></div>
        <div class="col-span-2">
          <span class="text-ink-muted">UID:</span>
          <code class="text-xs font-mono text-ink-muted ml-1">{detail.uid}</code>
        </div>
      </div>

      <!-- actions -->
      <div class="p-4 space-y-3">
        {#if actionError}
          <p class="text-xs text-status-error">{actionError}</p>
        {/if}

        <p class="text-xs uppercase tracking-wider text-ink-muted font-medium">Actions</p>

        <!-- Rename -->
        {#if editingName}
          <div class="flex gap-2 items-center">
            <input class="input flex-1 text-sm" bind:value={renameValue} placeholder="New name" />
            <Button variant="primary" onclick={doRename} disabled={actionLoading !== null}>Save</Button>
            <Button variant="ghost" onclick={() => editingName = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startRename} disabled={actionLoading !== null}>
            <Icon icon="lucide:pencil" width={14} class="mr-1" /> Rename
          </Button>
        {/if}

        <!-- Set Level -->
        {#if editingLevel}
          <div class="flex gap-2 items-center">
            <input class="input w-24 text-sm" type="number" min="1" max="80" bind:value={levelValue} />
            <Button variant="primary" onclick={doSetLevel} disabled={actionLoading !== null}>Set</Button>
            <Button variant="ghost" onclick={() => editingLevel = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startLevel} disabled={actionLoading !== null}>
            <Icon icon="lucide:trending-up" width={14} class="mr-1" /> Set Level
          </Button>
        {/if}

        <!-- Tech Points -->
        {#if editingTech}
          <div class="flex gap-2 items-center flex-wrap">
            <label class="text-xs text-ink-muted">Tech:
              <input class="input w-20 text-sm ml-1" type="number" min="0" bind:value={techPoints} />
            </label>
            <label class="text-xs text-ink-muted">Ancient:
              <input class="input w-20 text-sm ml-1" type="number" min="0" bind:value={bossTechPoints} />
            </label>
            <Button variant="primary" onclick={doTechPoints} disabled={actionLoading !== null}>Set</Button>
            <Button variant="ghost" onclick={() => editingTech = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startTech} disabled={actionLoading !== null}>
            <Icon icon="lucide:flask-conical" width={14} class="mr-1" /> Edit Tech Points
          </Button>
        {/if}

        <!-- Stats -->
        {#if editingStats}
          <div class="grid grid-cols-3 gap-2 text-sm">
            {#each [{key:'max_hp',label:'Max HP'},{key:'max_sp',label:'Max SP'},{key:'attack',label:'Attack'},{key:'weight',label:'Weight'},{key:'capture_rate',label:'Capture'},{key:'work_speed',label:'Work Spd'}] as stat}
              <label class="text-xs text-ink-muted block">
                {stat.label}
                <input class="input w-full text-sm mt-0.5" type="number" min="0" bind:value={stats[stat.key as keyof typeof stats]} />
              </label>
            {/each}
            <div class="col-span-3">
              <label class="text-xs text-ink-muted">
                Unused Stat Points
                <input class="input w-24 text-sm mt-0.5" type="number" min="0" bind:value={stats.unused_stat_points} />
              </label>
            </div>
          </div>
          <div class="flex gap-2 mt-2">
            <Button variant="primary" onclick={doStats} disabled={actionLoading !== null}>Apply Stats</Button>
            <Button variant="ghost" onclick={() => editingStats = false}>Cancel</Button>
          </div>
        {:else}
          <Button variant="secondary" onclick={startStats} disabled={actionLoading !== null}>
            <Icon icon="lucide:activity" width={14} class="mr-1" /> Edit Stats
          </Button>
        {/if}

        <div class="border-t border-line/20 pt-3 flex flex-wrap gap-2">
          <Button variant="secondary" onclick={handleResetTimestamp} disabled={actionLoading !== null}>
            <Icon icon="lucide:clock" width={14} class="mr-1" /> Reset Timestamp
          </Button>
          <Button variant="secondary" onclick={handleViewingCage} disabled={actionLoading !== null}>
            <Icon icon="lucide:unlock" width={14} class="mr-1" /> Unlock Viewing Cage
          </Button>
          <Button variant="secondary" onclick={handleUnlockTechs} disabled={actionLoading !== null}>
            <Icon icon="lucide:graduation-cap" width={14} class="mr-1" /> Unlock All Techs
          </Button>
          <Button variant="secondary" onclick={handleMaxAbilities} disabled={actionLoading !== null}>
            <Icon icon="lucide:zap" width={14} class="mr-1" /> Max All Abilities
          </Button>
        </div>

        <!-- Delete (danger) -->
        <div class="border-t border-line/20 pt-3">
          <Button variant="danger" onclick={handleDelete} disabled={actionLoading !== null}>
            <Icon icon="lucide:trash-2" width={14} class="mr-1" /> Delete Player
          </Button>
        </div>
      </div>
    {/if}
  </div>
</div>
