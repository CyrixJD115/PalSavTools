<script lang="ts">
  // Single inventory tile — a square slot showing item icon + count badge.
  // Empty slots render as a faint outline; occupied slots show the icon with
  // a count badge in the bottom-right and a subtle rarity border.
  //
  // Interactions:
  //   - hover  → shows ItemTooltip (passed via the `tooltip` snippet)
  //   - click  → fires onclick(item)
  //   - right-click (contextmenu) → fires oncontextmenu(item, event)
  //
  // Note: the prop is named `item` (not `slot`) because Svelte 5 reserves the
  // `slot` attribute for legacy slots — passing `slot={...}` to a child
  // component triggers a compile error.
  import Icon from '@iconify/svelte';
  import { itemIconUrl, imgOnError, peekItem, prettyItemId } from '$lib/utils/items';
  import type { ContainerItemSlot } from '$types/index';
  import type { Snippet } from 'svelte';

  let {
    item,
    empty = false,
    size = 'md',
    placeholderIcon = 'lucide:circle-dashed',
    onclick,
    oncontextmenu,
    tooltip,
  }: {
    item: ContainerItemSlot | null;
    empty?: boolean;
    size?: 'sm' | 'md' | 'lg';
    /** lucide/iconify icon shown in empty slots — pass a type-specific silhouette
     *  (e.g. 'lucide:shield' on the shield slot) for equipment readability. */
    placeholderIcon?: string;
    onclick?: (item: ContainerItemSlot) => void;
    oncontextmenu?: (item: ContainerItemSlot, e: MouseEvent) => void;
    tooltip?: Snippet<[ContainerItemSlot]>;
  } = $props();

  const sizeClass = $derived(
    { sm: 'w-9 h-9', md: 'w-12 h-12', lg: 'w-14 h-14' }[size]
  );
  const iconSize = $derived({ sm: 'w-7 h-7', md: 'w-9 h-9', lg: 'w-11 h-11' }[size]);

  let hover = $state(false);

  const meta = $derived(item ? peekItem(item.static_id) : null);
  const displayName = $derived(
    meta?.name || (item?.static_id ? prettyItemId(item.static_id) : '') || ''
  );
  const isEmpty = $derived(empty || !item || item.count <= 0 || !item.static_id);

  // Variant indicator (top-left dot) — color-coded by dynamic-item type so a
  // weapon/armor/egg reads at a glance. Plain stackable items have no dot.
  const variantColor = $derived.by(() => {
    const t = item?.dynamic?.type;
    if (!t) return '';
    if (t === 'weapon') return 'bg-rose-400';
    if (t === 'armor') return 'bg-sky-400';
    if (t === 'egg') return 'bg-amber-400';
    return 'bg-ink-muted';
  });

  function handleClick() {
    if (!isEmpty && item && onclick) onclick(item);
  }
  function handleContext(e: MouseEvent) {
    if (!isEmpty && item && oncontextmenu) {
      e.preventDefault();
      oncontextmenu(item, e);
    }
  }
</script>

{#if isEmpty}
  <!-- empty slot: non-interactive placeholder -->
  <div
    class="relative {sizeClass} rounded-4 border border-line/30 bg-bg-deep/40 select-none"
    aria-label="Empty slot"
  >
    <Icon icon={placeholderIcon} width={size === 'sm' ? 14 : size === 'lg' ? 20 : 17} class="text-line/40 absolute inset-0 m-auto" />
  </div>
{:else}
  <button
    type="button"
    class="relative {sizeClass} rounded-4 border border-line/60 bg-bg-deep hover:border-accent/60 hover:bg-bg-hover cursor-pointer transition-fast select-none"
    aria-label={displayName}
    onclick={handleClick}
    oncontextmenu={handleContext}
    onmouseenter={() => (hover = true)}
    onmouseleave={() => (hover = false)}
  >
    <img
      src={itemIconUrl(meta?.icon ?? null)}
      alt={displayName}
      class="{iconSize} object-contain absolute inset-0 m-auto p-0.5"
      onerror={imgOnError}
      loading="lazy"
    />
    <!-- count badge: bottom-right -->
    {#if item!.count > 1}
      <span class="absolute -bottom-1.5 -right-1.5 min-w-[1.1rem] h-[1.1rem] px-1 flex items-center justify-center rounded-full bg-accent text-white text-[10px] font-bold tabular-nums border border-bg-surface shadow">
        {item!.count > 9999 ? '9k+' : item!.count}
      </span>
    {/if}
    <!-- dynamic indicator (weapon/armor/egg): color-coded top-left dot -->
    {#if item!.dynamic_id && variantColor}
      <span
        class="absolute -top-1 -left-1 w-2.5 h-2.5 rounded-full {variantColor} border border-bg-surface"
        title={item!.dynamic?.type ? item!.dynamic.type.charAt(0).toUpperCase() + item!.dynamic.type.slice(1) : 'Unique item'}
      ></span>
    {/if}

    <!-- hover tooltip -->
    {#if hover && tooltip}
      <div class="absolute z-50 left-full top-0 ml-2">
        {@render tooltip(item!)}
      </div>
    {/if}
  </button>
{/if}
