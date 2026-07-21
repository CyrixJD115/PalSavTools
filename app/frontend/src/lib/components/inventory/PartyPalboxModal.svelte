<script lang="ts">
  // Party/Pal Box modal — wraps PartyPalboxPanel in the standard modal shell.
  import Icon from '@iconify/svelte';
  import { t } from '$stores/index';
  import PartyPalboxPanel from './PartyPalboxPanel.svelte';

  let {
    uid,
    partyId,
    palboxId,
    onclose,
  }: {
    uid: string;
    partyId: string | null;
    palboxId: string | null;
    onclose: () => void;
  } = $props();
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center" onclick={onclose} onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onclose()} role="dialog" tabindex="-1">
  <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="relative bg-bg-surface border border-line/40 rounded-6 shadow-xl max-w-3xl w-full mx-4 max-h-[80vh] flex flex-col animate-scale-in"
    onclick={(e: MouseEvent) => e.stopPropagation()}
    onkeydown={() => {}}
  >
    <div class="flex items-center justify-between p-4 border-b border-line/20 shrink-0">
      <div class="flex items-center gap-2">
        <Icon icon="lucide:paw-print" width={18} class="text-accent" />
        <h2 class="text-lg font-bold heading-gradient">{$t('web.inventory.party_palbox_title', 'Party & Pal Box')}</h2>
      </div>
      <button class="text-ink-muted hover:text-ink-primary transition-fast" onclick={onclose}>
        <Icon icon="lucide:x" width={20} />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto min-h-0">
      <PartyPalboxPanel {uid} {partyId} {palboxId} />
    </div>
  </div>
</div>
