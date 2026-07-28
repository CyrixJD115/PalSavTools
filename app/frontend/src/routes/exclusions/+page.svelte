<script lang="ts">
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import SaveGate from '$components/ui/SaveGate.svelte';
  import Card from '$components/ui/Card.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import EmptyState from '$components/ui/EmptyState.svelte';
  import Button from '$components/ui/Button.svelte';
  import {
    protection, saveEditLocked, rulesForTargetType,
    removeRule, toggleAction, setEditLocked,
  } from '$stores/protection';
  import type { ProtectionRule, ProtectionTargetType, ProtectionAction } from '$types/index';

  // Edit lock is a derived store; track locally for the toggle.
  let lockBusy = $state(false);

  async function onToggleLock() {
    lockBusy = true;
    try {
      await setEditLocked(!$saveEditLocked);
      toast.success($t(`web.protection.edit_lock_${!$saveEditLocked ? 'on' : 'off'}`));
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

  // Group rules by target type for the three columns.
  const playerRules = $derived(
    [...rulesForTargetType('player')].sort((a, b) => a.target_id.localeCompare(b.target_id)),
  );
  const guildRules = $derived(
    [...rulesForTargetType('guild')].sort((a, b) => a.target_id.localeCompare(b.target_id)),
  );
  const baseRules = $derived(
    [...rulesForTargetType('base')].sort((a, b) => a.target_id.localeCompare(b.target_id)),
  );

  const totalRules = $derived(playerRules.length + guildRules.length + baseRules.length);

  const columns: { type: ProtectionTargetType; icon: string; titleKey: string; rules: ProtectionRule[] }[] = $derived([
    { type: 'player', icon: 'lucide:users', titleKey: 'web.protection.players', rules: playerRules },
    { type: 'guild', icon: 'lucide:shield', titleKey: 'web.protection.guilds', rules: guildRules },
    { type: 'base', icon: 'lucide:home', titleKey: 'web.protection.bases', rules: baseRules },
  ]);

  // Shorten UIDs for display (first 8 chars).
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
    </div>

    <!-- Master edit lock card -->
    <Card>
      <div class="p-4 flex items-center justify-between gap-4">
        <div class="flex items-start gap-3">
          <div class="mt-0.5 text-accent">
            <Icon icon={$saveEditLocked ? 'lucide:lock' : 'lucide:unlock'} width={22} />
          </div>
          <div>
            <div class="text-sm font-semibold text-ink-primary">{$t('web.protection.edit_lock')}</div>
            <div class="text-xs text-ink-muted">{$t('web.protection.edit_lock_desc')}</div>
          </div>
        </div>
        <div class="flex items-center gap-3">
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

    <!-- Per-entity rule columns -->
    {#if totalRules === 0}
      <Card>
        <div class="p-8">
          <EmptyState icon="lucide:shield-off" title={$t('web.protection.empty')}>
          </EmptyState>
        </div>
      </Card>
    {:else}
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        {#each columns as col (col.type)}
          <Card>
            <div class="p-4 border-b border-line/40 flex items-center gap-2">
              <Icon icon={col.icon} width={16} class="text-ink-muted" />
              <span class="text-xs uppercase tracking-wider text-ink-muted">
                {$t(col.titleKey)}
              </span>
              <Badge tone="neutral" class="ml-auto">{col.rules.length}</Badge>
            </div>
            <div class="divide-y divide-line/20">
              {#each col.rules as rule (rule.id)}
                <div class="p-3 flex items-center gap-2 hover:bg-bg-hover/50 transition-fast">
                  <code class="text-xs text-ink-primary font-mono">{shortId(rule.target_id)}</code>

                  <!-- Action toggles -->
                  <div class="flex items-center gap-1 ml-auto">
                    <button
                      class="p-1 rounded transition-fast {rule.actions.includes('delete') ? 'text-status-error bg-status-error/10' : 'text-ink-muted hover:bg-bg-hover'}"
                      title={$t('web.protection.action_delete')}
                      onclick={() => onToggleAction(rule, 'delete')}
                    >
                      <Icon icon="lucide:trash-2" width={14} />
                    </button>
                    <button
                      class="p-1 rounded transition-fast {rule.actions.includes('edit') ? 'text-status-warning bg-status-warning/10' : 'text-ink-muted hover:bg-bg-hover'}"
                      title={$t('web.protection.action_edit')}
                      onclick={() => onToggleAction(rule, 'edit')}
                    >
                      <Icon icon="lucide:pencil" width={14} />
                    </button>
                  </div>

                  {#if col.type === 'guild' && rule.cascade}
                    <Badge tone="accent" class="text-[10px] px-1.5 py-0.5">
                      {$t('web.protection.cascade')}
                    </Badge>
                  {/if}

                  <button
                    class="p-1 rounded text-ink-muted hover:text-status-error hover:bg-status-error/10 transition-fast"
                    title={$t('web.protection.remove')}
                    onclick={() => onRemove(rule)}
                  >
                    <Icon icon="lucide:x" width={14} />
                  </button>
                </div>
              {/each}
            </div>
          </Card>
        {/each}
      </div>
    {/if}
  </div>
</SaveGate>
