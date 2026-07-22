<script lang="ts">
  /**
   * ChainTooltip — floating hover card for a dendrogram node.
   *
   * Mirrors `MapTooltip.svelte` (absolute-positioned HTML overlay, clamped to
   * viewport). Shows large icon, display name, gender, all passives, source
   * type, and step index for bred nodes.
   */
  import Icon from '@iconify/svelte';
  import { assetUrl, imgOnError } from '$lib/utils/assetUrl';
  import type { TreeNode } from '$lib/breeding/dendrogram/types';

  interface Props {
    node: TreeNode | null;
    x: number;
    y: number;
    passiveName?: (asset: string) => string;
  }

  let {
    node,
    x,
    y,
    passiveName = (asset: string) => asset,
  }: Props = $props();

  // Position relative to viewport (the tooltip is a child of the dendrogram
  // container, but x/y are client coords — so we use position: fixed).
  let tx = $derived(Math.min(x + 16, (typeof window !== 'undefined' ? window.innerWidth : 9999) - 280));
  let ty = $derived(Math.max(y - 50, 8));

  const sourceMeta = {
    owned: { icon: 'lucide:package', label: 'Owned', cls: 'text-accent' },
    selected: { icon: 'lucide:hand', label: 'Selected', cls: 'text-emerald-400' },
    wild: { icon: 'lucide:trees', label: 'Wild', cls: 'text-amber-400' },
  } as const;

  function srcMeta(type?: string) {
    if (!type) return null;
    return sourceMeta[type as keyof typeof sourceMeta] ?? null;
  }
</script>

{#if node}
  <div
    class="fixed z-50 pointer-events-none max-w-[260px] rounded-8 border border-accent/40 bg-bg-deep/95 backdrop-blur-md shadow-card-lg"
    style="left: {tx}px; top: {ty}px;"
  >
    <div class="flex items-start gap-2 p-2.5">
      <img
        src={assetUrl(node.icon)}
        alt=""
        class="w-12 h-12 rounded-6 object-cover border border-line/60 shrink-0"
        onerror={imgOnError}
      />
      <div class="min-w-0 space-y-0.5">
        <div class="flex items-center gap-1.5">
          <span class="font-bold text-sm text-ink-emphasis truncate">{node.display}</span>
          {#if node.gender === 'Male'}
            <Icon icon="lucide:mars" width={12} class="text-accent-light shrink-0" />
          {:else if node.gender === 'Female'}
            <Icon icon="lucide:venus" width={12} class="text-pink-300 shrink-0" />
          {/if}
        </div>
        <div class="text-[10px] text-ink-dim font-mono">{node.tribe}</div>

        {#if node.isBred && node.stepIndex !== undefined}
          <div class="text-[10px] text-accent-cyan">
            Step {node.stepIndex + 1} · Bred
          </div>
        {:else if srcMeta(node.sourceType)}
          {@const m = srcMeta(node.sourceType)!}
          <div class="text-[10px] {m.cls} flex items-center gap-1">
            <Icon icon={m.icon} width={10} class="inline" />{m.label}
          </div>
        {/if}
        {#if node.isTarget}
          <div class="text-[10px] text-accent font-semibold flex items-center gap-1">
            <Icon icon="lucide:target" width={10} class="inline" />Target
          </div>
        {/if}
      </div>
    </div>

    {#if node.passives.length}
      <div class="px-2.5 pb-2.5 pt-0.5 flex flex-wrap gap-1 border-t border-line/30">
        {#each node.passives as passive}
          <span class="chip text-[9px] px-1.5 py-0">{passiveName(passive)}</span>
        {/each}
      </div>
    {/if}
  </div>
{/if}
