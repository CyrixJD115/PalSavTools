<script lang="ts">
  // Tech Tree modal — wraps TechTreePanel in the standard modal shell.
  // The panel itself is shared with the inline Tech Tree tab on the inventory page.
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import TechTreePanel from './TechTreePanel.svelte';

  let { uid, playerName, onclose }: {
    uid: string;
    playerName: string;
    onclose: () => void;
  } = $props();
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()} role="dialog" tabindex="-1">
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-5xl w-full mx-4 h-[85vh] flex flex-col animate-scale-in"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <!-- header -->
    <div class="flex items-center justify-between p-4 border-b border-line/20 shrink-0">
      <div class="flex items-center gap-2 min-w-0">
        <Icon icon="lucide:git-branch" width={18} class="text-accent shrink-0" />
        <h2 class="text-lg font-bold heading-gradient truncate">
          {$t('web.inventory.tech_tree_title', 'Tech Tree')}
          <span class="text-xs text-ink-muted font-normal ml-1">· {playerName}</span>
        </h2>
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast shrink-0" onclick={onclose} aria-label="Close">
        <Icon icon="lucide:x" width={20} />
      </button>
    </div>

    <!-- panel fills the remaining space -->
    <div class="flex-1 min-h-0">
      <TechTreePanel {uid} />
    </div>
  </div>
</div>
