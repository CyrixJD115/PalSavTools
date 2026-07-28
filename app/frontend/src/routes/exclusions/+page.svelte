<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import Button from '$components/ui/Button.svelte';
  import Spinner from '$components/ui/Spinner.svelte';
  import {
    protection, saveEditLocked, rulesByType,
    removeRule, toggleAction, setEditLocked,
    entityLabels, refreshEntityLabels, labelFor,
  } from '$stores/protection';
  import type { ProtectionRule, ProtectionTargetType, ProtectionAction } from '$types/index';

  let lockBusy = $state(false);
  let refreshing = $state(false);

  onMount(() => {
    void refreshLabels();
  });

  async function refreshLabels() {
    refreshing = true;
    try { await refreshEntityLabels(); } finally { refreshing = false; }
  }

  async function onToggleLock() {
    lockBusy = true;
    try {
      await setEditLocked(!$saveEditLocked);
      toast.success(!$saveEditLocked
        ? $t('web.protection.edit_lock_on')
        : $t('web.protection.edit_lock_off'));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      lockBusy = false;
    }
  }

  function onRemove(rule: ProtectionRule) {
    removeRule(rule.id);
    toast.success($t('web.toast.protection_removed'));
  }

  function onToggleAction(rule: ProtectionRule, action: ProtectionAction) {
    toggleAction(rule.id, action);
  }

  // Reactive rule stores — recomputed whenever the protection store changes
  // (add/remove/toggle/load). Using derived stores (not get() snapshots) is
  // what keeps the page in sync without manual refetch.
  const playerRulesStore = rulesByType('player');
  const guildRulesStore = rulesByType('guild');
  const baseRulesStore = rulesByType('base');
  const palRulesStore = rulesByType('pal');

  const totalRules = $derived($playerRulesStore.length + $guildRulesStore.length + $baseRulesStore.length + $palRulesStore.length);

  // Columns config — icon per type, accent color for the header.
  const TARGET_META: Record<ProtectionTargetType, { icon: string; accent: string; titleKey: string }> = {
    player: { icon: 'lucide:user', accent: 'text-accent', titleKey: 'web.protection.players' },
    guild:  { icon: 'lucide:users-round', accent: 'text-status-success', titleKey: 'web.protection.guilds' },
    base:   { icon: 'lucide:home', accent: 'text-status-warning', titleKey: 'web.protection.bases' },
    pal:    { icon: 'lucide:paw-print', accent: 'text-pink-400', titleKey: 'web.protection.pals' },
  };

  const columns = $derived([
    { type: 'player' as ProtectionTargetType, rules: $playerRulesStore },
    { type: 'guild' as ProtectionTargetType, rules: $guildRulesStore },
    { type: 'base' as ProtectionTargetType, rules: $baseRulesStore },
    { type: 'pal' as ProtectionTargetType, rules: $palRulesStore },
  ]);

  // Shorten UIDs for the secondary line under the name.
  function shortId(uid: string): string {
    return uid.length > 12 ? `${uid.slice(0, 8)}…` : uid;
  }
</script>

<SaveGate icon="lucide:shield-off">
  <div class="p-6 max-w-6xl mx-auto space-y-4 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold heading-gradient">{$t('web.protection.title')}</h1>
        <p class="text-xs text-ink-muted">{$t('web.protection.description')}</p>
      </div>
      <Button variant="ghost" onclick={refreshLabels} disabled={refreshing} title={$t('web.protection.refresh')}>
        <Icon icon={refreshing ? 'lucide:loader-2' : 'lucide:refresh-cw'} width={16} class={refreshing ? 'animate-spin' : ''} />
      </Button>
    </div>

    <!-- Master edit lock card -->
    <Card>
      <div class="p-4 flex items-center justify-between gap-4">
        <div class="flex items-start gap-3 min-w-0">
          <div class="mt-0.5 {$saveEditLocked ? 'text-status-warning' : 'text-ink-muted'}">
            <Icon icon={$saveEditLocked ? 'lucide:lock' : 'lucide:unlock'} width={22} />
          </div>
          <div class="min-w-0">
            <div class="text-sm font-semibold text-ink-primary">{$t('web.protection.edit_lock')}</div>
            <div class="text-xs text-ink-muted">{$t('web.protection.edit_lock_desc')}</div>
          </div>
        </div>
        <div class="flex items-center gap-3 shrink-0">
          {#if $saveEditLocked}
            <Badge tone="warning">{$t('web.protection.edit_lock_on')}</Badge>
          {:else}
            <Badge tone="neutral">{$t('web.protection.edit_lock_off')}</Badge>
          {/if}
          <Button
            variant={$saveEditLocked ? 'danger' : 'primary'}
            loading={lockBusy}
            onclick={onToggleLock}
          >
            <Icon icon={$saveEditLocked ? 'lucide:unlock' : 'lucide:lock'} width={16} />
            {$saveEditLocked ? $t('web.protection.edit_lock_off') : $t('web.protection.edit_lock_on')}
          </Button>
        </div>
      </div>
    </Card>

    {#if $saveEditLocked}
      <div class="flex items-center gap-2 px-4 py-2 rounded-md bg-status-warning/10 border border-status-warning/30 text-xs text-status-warning">
        <Icon icon="lucide:alert-triangle" width={14} />
        {$t('web.protection.save_locked')}
      </div>
    {/if}

    {#if !$entityLabels.loaded && refreshing}
      <Card><div class="flex justify-center py-12"><Spinner size={24} /></div></Card>
    {:else if totalRules === 0}
      <Card>
        <div class="p-8">
          <EmptyState icon="lucide:shield-off" title={$t('web.protection.empty')} />
        </div>
      </Card>
    {:else}
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {#each columns as col (col.type)}
          {@const meta = TARGET_META[col.type]}
          <Card>
            <!-- Column header -->
            <div class="p-3.5 border-b border-line/40 flex items-center gap-2">
              <Icon icon={meta.icon} width={16} class={meta.accent} />
              <span class="text-xs uppercase tracking-wider text-ink-muted font-medium">
                {$t(meta.titleKey)}
              </span>
              <Badge tone="neutral" class="ml-auto">{col.rules.length}</Badge>
            </div>

            <!-- Rule rows -->
            {#if col.rules.length === 0}
              <div class="p-4 text-xs text-ink-muted italic text-center">
                {$t('web.protection.none')}
              </div>
            {:else}
              <div class="divide-y divide-line/20">
                {#each col.rules as rule (rule.id)}
                  <div class="p-3 hover:bg-bg-hover/50 transition-fast">
                    <!-- Top line: target icon + resolved name + remove -->
                    <div class="flex items-center gap-2">
                      <Icon icon={meta.icon} width={14} class={`${meta.accent} shrink-0`} />
                      <span class="text-sm font-medium text-ink-primary truncate flex-1">
                        {labelFor(col.type, rule.target_id)}
                      </span>
                      <button
                        class="p-1 rounded text-ink-muted hover:text-status-error hover:bg-status-error/10 transition-fast shrink-0"
                        title={$t('web.protection.remove')}
                        onclick={() => onRemove(rule)}
                      >
                        <Icon icon="lucide:trash-2" width={14} />
                      </button>
                    </div>
                    <!-- Second line: raw ID + cascade badge -->
                    <div class="flex items-center gap-1.5 mt-1 pl-[22px]">
                      <code class="text-[10px] text-ink-muted font-mono">{shortId(rule.target_id)}</code>
                      {#if col.type === 'guild' && rule.cascade}
                        <Badge tone="accent" class="text-[9px] px-1 py-0 leading-tight">
                          {$t('web.protection.cascade')}
                        </Badge>
                      {/if}
                    </div>
                    <!-- Action chips: toggle delete / edit -->
                    <div class="flex items-center gap-1.5 mt-2 pl-[22px]">
                      <span class="text-[10px] text-ink-muted mr-0.5">{$t('web.protection.protects')}:</span>
                      <button
                        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-fast border
                          {rule.actions.includes('delete')
                            ? 'border-status-error/40 bg-status-error/10 text-status-error'
                            : 'border-line/40 text-ink-muted hover:bg-bg-hover'}"
                        title={$t('web.protection.action_delete')}
                        onclick={() => onToggleAction(rule, 'delete')}
                      >
                        <Icon icon="lucide:ban" width={10} />
                        {$t('web.protection.action_delete')}
                      </button>
                      <button
                        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium transition-fast border
                          {rule.actions.includes('edit')
                            ? 'border-status-warning/40 bg-status-warning/10 text-status-warning'
                            : 'border-line/40 text-ink-muted hover:bg-bg-hover'}"
                        title={$t('web.protection.action_edit')}
                        onclick={() => onToggleAction(rule, 'edit')}
                      >
                        <Icon icon="lucide:pencil" width={10} />
                        {$t('web.protection.action_edit')}
                      </button>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </Card>
        {/each}
      </div>
    {/if}
  </div>
</SaveGate>
