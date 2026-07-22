<script lang="ts">
  /**
   * AdjustRadiusModal — set a base camp's ``area_range`` via a percentage slider.
   *
   * Ports the PST desktop ``RadiusPreviewDialog`` UX: 100% = 3500 (default),
   * clamped to [0%, 285%] = [0, 10000]. The numeric ``area_range`` follows
   * ``percent * 35`` exactly as in PST's ``map_tab.py:1593``.
   *
   * Live preview ring is drawn on the map via the ``onPreview`` callback —
   * the parent temporarily overrides the selected base's ``area_range`` so
   * the engine re-renders the ring before commit.
   */

  import { t } from '$stores/index';
  import { toast } from '$stores/toast';
  import { api } from '$lib/api/client';
  import Icon from '@iconify/svelte';
  import type { MapBase } from '$types/index';

  interface Props {
    open: boolean;
    base: MapBase | null;
    onclose: () => void;
    /** Called with the in-progress radius so the parent can preview-render. */
    onpreview?: (radius: number) => void;
    /** Called after a successful commit (parent should refetch map data). */
    oncommitted?: () => void;
  }

  let { open = false, base = null, onclose, onpreview, oncommitted }: Props = $props();

  // percent slider state; 100% == 3500 (default), range 0..285
  let percent = $state(100);
  let saving = $state(false);

  // Initialize percent when base changes
  $effect(() => {
    if (open && base) {
      percent = Math.round((base.area_range ?? 3500) / 35);
    }
  });

  let actualRadius = $derived(percent * 35);

  // Live preview: emit when percent changes
  $effect(() => {
    if (open && base) {
      onpreview?.(actualRadius);
    }
  });

  function close() {
    // Reset preview to actual before closing
    if (base) onpreview?.(base.area_range);
    onclose();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }

  async function apply() {
    if (!base) return;
    saving = true;
    try {
      await api.setBaseRadius(base.id, { radius: actualRadius });
      toast.success($t('web.toast.radius_updated', { percent, radius: actualRadius }));
      oncommitted?.();
      onclose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : $t('web.toast.radius_update_failed'));
    } finally {
      saving = false;
    }
  }

  function reset() {
    percent = 100;
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open && base}
  <div
    class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
    role="presentation"
  >
    <div
      class="w-full max-w-md card shadow-card-lg border-accent-cyan/40 border-2"
      role="dialog"
      aria-modal="true"
      aria-label={$t('web.map.adjust_radius_title')}
    >
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:circle-dashed" width={18} class="text-accent-cyan" />
          {$t('web.map.adjust_radius_title')}
        </h2>
        <button class="text-ink-dim hover:text-ink-primary transition-fast" onclick={close} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <div class="space-y-4">
        <div class="text-xs text-ink-muted">
          {$t('web.map.adjust_radius_for', { guild: base.guild_name || base.id.slice(0, 8) })}
        </div>

        <!-- Percent display -->
        <div class="text-center">
          <div class="text-4xl font-bold text-accent-cyan">{percent}<span class="text-xl">%</span></div>
          <div class="text-xs text-ink-dim font-mono mt-1">area_range = {actualRadius}</div>
        </div>

        <!-- Slider -->
        <input
          type="range"
          min="0"
          max="285"
          step="1"
          bind:value={percent}
          class="w-full accent-accent-cyan"
        />

        <!-- Quick presets -->
        <div class="flex gap-2 justify-center">
          <button
            class="px-2 py-1 text-[10px] rounded-3 border border-line/30 bg-bg-elevated/60
                   hover:border-accent-cyan/50 text-ink-secondary transition-fast"
            onclick={() => (percent = 50)}
          >50%</button>
          <button
            class="px-2 py-1 text-[10px] rounded-3 border border-line/30 bg-bg-elevated/60
                   hover:border-accent-cyan/50 text-ink-secondary transition-fast"
            onclick={() => (percent = 100)}
          >100% (default)</button>
          <button
            class="px-2 py-1 text-[10px] rounded-3 border border-line/30 bg-bg-elevated/60
                   hover:border-accent-cyan/50 text-ink-secondary transition-fast"
            onclick={() => (percent = 200)}
          >200%</button>
          <button
            class="px-2 py-1 text-[10px] rounded-3 border border-line/30 bg-bg-elevated/60
                   hover:border-accent-cyan/50 text-ink-secondary transition-fast"
            onclick={reset}
          >{$t('web.map.reset')}</button>
        </div>

        <div class="rounded-6 bg-status-amber/10 border border-status-amber/25 p-3 text-[11px] text-status-amber">
          <Icon icon="lucide:info" width={12} class="inline mr-1" />
          {$t('web.map.radius_reload_hint')}
        </div>
      </div>

      <div class="flex justify-end gap-2 mt-5">
        <button onclick={close} class="btn btn-ghost">{$t('web.common.cancel')}</button>
        <button
          onclick={apply}
          disabled={saving}
          class="btn btn-primary"
        >
          {#if saving}
            <Icon icon="lucide:loader-2" width={14} class="animate-spin inline mr-1" />
            {$t('web.common.saving')}
          {:else}
            {$t('web.common.apply')}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
