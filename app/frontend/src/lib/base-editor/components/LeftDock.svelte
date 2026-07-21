<script lang="ts">
  // Left-edge dock with the Levels panel. Port of LeftDock.tsx + LevelsPanel.tsx.
  // Collapsible + drag-resizable; persists width/collapsed state to localStorage.
  // Publishes its width as a CSS var `--be-left-dock-width` on document root so
  // the viewport overlays can offset accordingly.
  import Icon from "@iconify/svelte";
  import { t } from "$stores/index";
  import { editor, isLevelVisible, anyLevelsHidden } from "../core/store.svelte";
  import { findPalbox } from "../core/campGeometry";
  import { buildLevelIndex } from "../core/levels";
  import { getTypeEntry } from "../core/objectTypes";
  import type { PlacedObject } from "../core/types";

  const COLLAPSED_KEY = "pst.base-editor.leftDock.collapsed";
  const WIDTH_KEY = "pst.base-editor.leftDock.width";
  const MIN_WIDTH = 200;
  const MAX_WIDTH = 520;
  const DEFAULT_WIDTH = 280;
  const COLLAPSED_WIDTH = 32;

  let collapsed = $state(localStorage.getItem(COLLAPSED_KEY) === "1");
  let width = $state((() => {
    const v = Number(localStorage.getItem(WIDTH_KEY));
    return Number.isFinite(v) && v >= MIN_WIDTH && v <= MAX_WIDTH ? v : DEFAULT_WIDTH;
  })());

  // Persist.
  $effect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? "1" : "0");
      localStorage.setItem(WIDTH_KEY, String(width));
    } catch {
      // best-effort
    }
  });
  // Publish CSS var.
  $effect(() => {
    const px = collapsed ? COLLAPSED_WIDTH : width;
    document.documentElement.style.setProperty("--be-left-dock-width", `${px}px`);
  });

  // Drag-resize handle.
  let drag: { startX: number; startWidth: number } | null = null;
  function onHandleDown(e: PointerEvent) {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drag = { startX: e.clientX, startWidth: width };
  }
  function onHandleMove(e: PointerEvent) {
    if (!drag) return;
    width = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, drag.startWidth + (e.clientX - drag.startX)));
  }
  function onHandleUp(e: PointerEvent) {
    drag = null;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }

  // Levels data.
  let palboxZ = $derived(findPalbox(editor.objects).palbox?.position.z ?? null);
  let levelGroups = $derived(buildLevelIndex(editor.objects, palboxZ));

  let expandedLevels = $state<Set<number>>(new Set());
  function toggleExpanded(level: number) {
    const next = new Set(expandedLevels);
    if (next.has(level)) next.delete(level);
    else next.add(level);
    expandedLevels = next;
  }
  function typeBreakdownFor(objects: PlacedObject[]): { typeId: string; count: number; ids: string[] }[] {
    const byType = new Map<string, { typeId: string; count: number; ids: string[] }>();
    for (const o of objects) {
      const entry = byType.get(o.typeId);
      if (entry) { entry.count++; entry.ids.push(o.id); }
      else byType.set(o.typeId, { typeId: o.typeId, count: 1, ids: [o.id] });
    }
    return [...byType.values()].sort((a, b) => b.count - a.count);
  }
  function selectIds(ids: string[], shiftKey: boolean) {
    editor.setSelection(shiftKey ? [...new Set([...editor.selection, ...ids])] : ids);
  }
  let hidden = $derived(anyLevelsHidden(editor.hiddenLevels, editor.soloLevel));
</script>

<div
  class="shrink-0 h-full flex border-r border-line/60 bg-bg-surface transition-fast"
  style="width: {collapsed ? COLLAPSED_WIDTH : width}px;"
>
  <button
    type="button"
    class="w-8 h-full flex items-center justify-center text-ink-dim hover:text-ink-secondary border-r border-line/40"
    onclick={() => (collapsed = !collapsed)}
    title={collapsed ? $t("web.base_editor.expand_levels") : $t("web.base_editor.collapse_levels")}
    aria-expanded={!collapsed}
  >
    <Icon icon={collapsed ? "lucide:chevron-right" : "lucide:chevron-left"} width={14} />
  </button>

  {#if !collapsed}
    <div class="flex-1 min-w-0 overflow-y-auto p-2">
      <div class="flex items-center gap-2 mb-2">
        <Icon icon="lucide:layers" width={14} class="text-accent-light" />
        <h3 class="text-xs font-semibold uppercase tracking-widest text-ink-secondary flex-1">
          {$t("web.base_editor.levels")}
        </h3>
        <button
          type="button"
          class="text-[10px] text-accent-light hover:underline disabled:text-ink-dim disabled:no-underline"
          disabled={!hidden}
          onclick={() => editor.showAll()}
          title={hidden ? $t("web.base_editor.show_all_title") : $t("web.base_editor.nothing_hidden")}
        >
          {$t("web.base_editor.show_all")}
        </button>
      </div>

      {#if levelGroups.length === 0}
        <p class="text-[11px] text-ink-dim">{$t("web.base_editor.no_objects_loaded")}</p>
      {:else}
        <ul class="space-y-0.5">
          {#each levelGroups as { level, objects: levelObjects } (level)}
            {@const ids = levelObjects.map((o) => o.id)}
            {@const expanded = expandedLevels.has(level)}
            {@const visible = isLevelVisible(level, editor.hiddenLevels, editor.soloLevel)}
            {@const soloed = editor.soloLevel === level}
            {@const types = typeBreakdownFor(levelObjects).slice(0, 8)}
            {@const hiddenTypeCount = typeBreakdownFor(levelObjects).length - types.length}
            <li>
              <div class="flex items-center gap-1 py-0.5 {visible ? '' : 'opacity-50'}">
                <button
                  type="button"
                  class="w-4 text-ink-dim hover:text-ink-secondary text-xs"
                  onclick={() => toggleExpanded(level)}
                  aria-expanded={expanded}
                  title={expanded ? $t("web.base_editor.collapse") : $t("web.base_editor.expand_n_types", { n: String(typeBreakdownFor(levelObjects).length) })}
                >
                  {expanded ? "▾" : "▸"}
                </button>
                <button
                  type="button"
                  class="flex-1 text-left text-xs text-ink-secondary hover:text-ink-primary font-mono"
                  onclick={(e) => selectIds(ids, e.shiftKey)}
                  title={$t("web.base_editor.select_level", { level: String(level), count: String(ids.length) })}
                >
                  L{level} · {ids.length}
                </button>
                <button
                  type="button"
                  class="w-5 text-xs {visible ? 'text-ink-muted hover:text-ink-primary' : 'text-status-warning'}"
                  onclick={() => editor.toggleLevelHidden(level)}
                  title={visible ? $t("web.base_editor.hide_level") : $t("web.base_editor.show_level")}
                >
                  <Icon icon={visible ? "lucide:eye" : "lucide:eye-off"} width={12} />
                </button>
                <button
                  type="button"
                  class="w-5 text-xs {soloed ? 'text-accent-light' : 'text-ink-dim hover:text-ink-secondary'}"
                  onclick={() => editor.toggleSolo(level)}
                  title={soloed ? $t("web.base_editor.clear_solo") : $t("web.base_editor.solo_level", { level: String(level) })}
                >
                  <Icon icon="lucide:circle-dot" width={12} />
                </button>
              </div>
              {#if expanded}
                <ul class="ml-5 border-l border-line/40 pl-1.5 space-y-0.5">
                  {#each types as { typeId, count, ids: typeIds } (typeId)}
                    <li>
                      <button
                        type="button"
                        class="block w-full text-left text-[11px] text-ink-muted hover:text-ink-secondary py-0.5"
                        onclick={(e) => selectIds(typeIds, e.shiftKey)}
                        title={$t("web.base_editor.select_these", { count: String(count) })}
                      >
                        {getTypeEntry(typeId)?.name ?? typeId} ×{count}
                      </button>
                    </li>
                  {/each}
                  {#if hiddenTypeCount > 0}
                    <li class="text-[10px] text-ink-dim">{$t("web.base_editor.and_n_more", { n: String(hiddenTypeCount) })}</li>
                  {/if}
                </ul>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <!-- Drag-resize handle -->
    <div
      class="w-1 h-full cursor-ew-resize bg-line/40 hover:bg-accent/40 transition-fast"
      role="separator"
      onpointerdown={onHandleDown}
      onpointermove={onHandleMove}
      onpointerup={onHandleUp}
      title={$t("web.base_editor.resize")}
    ></div>
  {/if}
</div>
