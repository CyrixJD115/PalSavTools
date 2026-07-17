<script lang="ts">
  import type { Snippet } from 'svelte';
  import { saveLoaded, t } from '$stores/index';
  import EmptyState from '$components/ui/EmptyState.svelte';

  let {
    icon = 'lucide:file-x',
    children,
  }: { icon?: string; children: Snippet } = $props();
</script>

{#if !$saveLoaded}
  <div class="p-6 max-w-4xl mx-auto animate-fade-in">
    <div class="card">
      <EmptyState {icon} title={$t('web.save_gate.title')}>
        <p>{@html $t('web.save_gate.body')}</p>
      </EmptyState>
    </div>
  </div>
{:else}
  {@render children()}
{/if}
