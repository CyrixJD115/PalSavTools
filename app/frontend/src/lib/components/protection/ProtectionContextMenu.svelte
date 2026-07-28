<script lang="ts">
  // Right-click context menu for adding protection rules. Rendered at the
  // cursor position over a scrim that closes on outside click / Escape.
  //
  // Mirrors the ItemContextMenu pattern. Offers three actions: protect from
  // deletion, lock editing, or full protection (both).
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import { addRule, findRule } from '$stores/protection';
  import type { ProtectionTargetType, ProtectionAction } from '$types/index';

  let {
    targetType,
    targetId,
    targetName = '',
    x,
    y,
    onclose,
  }: {
    targetType: ProtectionTargetType;
    targetId: string;
    targetName?: string;
    x: number;
    y: number;
    onclose: () => void;
  } = $props();

  const menuW = 220;
  const menuH = 150;
  const adjustedX = $derived(Math.min(x, (typeof window !== 'undefined' ? window.innerWidth : 9999) - menuW - 8));
  const adjustedY = $derived(Math.min(y, (typeof window !== 'undefined' ? window.innerHeight : 9999) - menuH - 8));

  const existing = $derived(findRule(targetType, targetId));

  function protect(actions: ProtectionAction[]) {
    if (existing) {
      // Already has a direct rule — just merge the actions.
      const merged = Array.from(new Set([...existing.actions, ...actions]));
      // Re-add with merged actions (addRule dedups by id-shape; simplest is
      // to remove + re-add). But we don't have removeRule here cleanly —
      // instead, addRule skips if an identical rule exists, so we call it
      // with the union. If the union already matches, it's a no-op.
      // For now, the simpler UX: if a rule exists, do nothing (user edits
      // actions in the Protection tab). Toast informs them.
      toast.info($t('web.toast.protection_exists'));
    } else {
      addRule(targetType, targetId, actions, targetType === 'guild');
      toast.success($t('web.toast.protection_added'));
    }
    onclose();
  }

  const pickDelete = () => protect(['delete']);
  const pickEdit = () => protect(['edit']);
  const pickFull = () => protect(['delete', 'edit']);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class="fixed inset-0 z-50"
  onclick={onclose}
  oncontextmenu={(e: MouseEvent) => { e.preventDefault(); onclose(); }}
  onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()}
>
  <div
    class="absolute bg-bg-surface border border-line/60 rounded-6 shadow-xl py-1 text-sm animate-scale-in"
    style="left: {adjustedX}px; top: {adjustedY}px; width: {menuW}px;"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={(e: KeyboardEvent) => e.stopPropagation()}
    role="menu"
    tabindex={-1}
  >
    <div class="px-3 py-1.5 text-xs text-ink-muted border-b border-line/30 mb-1">
      {targetName || targetId}
    </div>
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-status-error hover:bg-status-error/10 transition-fast"
      onclick={pickDelete}
      role="menuitem"
    >
      <Icon icon="lucide:shield-off" width={14} />
      {$t('web.protection.add_delete')}
    </button>
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-status-warning hover:bg-status-warning/10 transition-fast"
      onclick={pickEdit}
      role="menuitem"
    >
      <Icon icon="lucide:pencil" width={14} />
      {$t('web.protection.add_edit')}
    </button>
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-left text-accent hover:bg-bg-hover transition-fast"
      onclick={pickFull}
      role="menuitem"
    >
      <Icon icon="lucide:shield-check" width={14} />
      {$t('web.protection.add_full')}
    </button>
  </div>
</div>
