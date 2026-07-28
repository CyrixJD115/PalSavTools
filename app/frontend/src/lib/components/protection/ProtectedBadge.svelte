<script lang="ts">
  // Tiny inline shield indicator shown next to a protected entity's name in
  // list pages. Reads the protection store reactively. Click is not handled
  // here — the badge is informational; full management is on the Protection
  // tab. Colored by the strongest action present (delete = red, edit = amber).
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import { findRule, protection } from '$stores/protection';
  import type { ProtectionTargetType } from '$types/index';

  let {
    targetType,
    targetId,
  }: {
    targetType: ProtectionTargetType;
    targetId: string;
  } = $props();

  const rule = $derived(findRule(targetType, targetId));
  const locked = $derived($protection.edit_locked);

  const shown = $derived(!!rule || locked);
  const tone = $derived(
    locked ? 'text-status-warning'
    : (rule?.actions.includes('delete') ? 'text-status-error' : 'text-status-warning'),
  );
  const tip = $derived(
    locked ? $t('web.protection.save_locked')
    : $t('web.protection.blocked_tooltip'),
  );
</script>

{#if shown}
  <span class="inline-flex items-center {tone}" title={tip}>
    <Icon icon="lucide:shield" width={12} />
  </span>
{/if}
