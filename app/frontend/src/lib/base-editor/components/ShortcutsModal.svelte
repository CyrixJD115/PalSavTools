<script lang="ts">
  // Keyboard cheat-sheet. Port of ShortcutsModal.tsx, restyled to match PST's
  // existing modal vocabulary (centered overlay + Card).
  import Icon from "@iconify/svelte";
  import { t } from "$stores/index";

  let { onclose }: { onclose: () => void } = $props();

  const groups: { titleKey: string; items: { keys: string[]; labelKey: string }[] }[] = [
    {
      titleKey: "web.base_editor.shortcuts.selection",
      items: [
        { keys: ["Click"], labelKey: "web.base_editor.sc_select" },
        { keys: ["Shift", "Click"], labelKey: "web.base_editor.sc_range" },
        { keys: ["Ctrl", "Click"], labelKey: "web.base_editor.sc_toggle" },
        { keys: ["Alt", "Click"], labelKey: "web.base_editor.sc_all_of_type" },
        { keys: ["Shift", "Drag"], labelKey: "web.base_editor.sc_marquee" },
        { keys: ["Ctrl", "A"], labelKey: "web.base_editor.sc_select_all" },
      ],
    },
    {
      titleKey: "web.base_editor.shortcuts.transform",
      items: [
        { keys: ["↑↓←→"], labelKey: "web.base_editor.sc_nudge" },
        { keys: ["PageUp", "PageDown"], labelKey: "web.base_editor.sc_raise_lower" },
        { keys: ["Q", "E"], labelKey: "web.base_editor.sc_rotate" },
        { keys: ["Shift", "Q/E"], labelKey: "web.base_editor.sc_group_rotate" },
        { keys: ["Ctrl", "D"], labelKey: "web.base_editor.sc_duplicate" },
        { keys: ["Delete"], labelKey: "web.base_editor.sc_delete" },
      ],
    },
    {
      titleKey: "web.base_editor.shortcuts.history",
      items: [
        { keys: ["Ctrl", "Z"], labelKey: "web.base_editor.sc_undo" },
        { keys: ["Ctrl", "Y"], labelKey: "web.base_editor.sc_redo" },
        { keys: ["Escape"], labelKey: "web.base_editor.sc_cancel" },
      ],
    },
    {
      titleKey: "web.base_editor.shortcuts.camera",
      items: [
        { keys: ["LMB Drag"], labelKey: "web.base_editor.sc_orbit" },
        { keys: ["Scroll"], labelKey: "web.base_editor.sc_zoom" },
        { keys: ["RMB Hold"], labelKey: "web.base_editor.sc_fly" },
        { keys: ["W A S D"], labelKey: "web.base_editor.sc_fly_move" },
        { keys: ["Q E (fly)"], labelKey: "web.base_editor.sc_fly_vertical" },
        { keys: ["Shift (fly)"], labelKey: "web.base_editor.sc_fly_fast" },
      ],
    },
    {
      titleKey: "web.base_editor.shortcuts.place",
      items: [
        { keys: ["Click (armed)"], labelKey: "web.base_editor.sc_place" },
        { keys: ["Shift", "Click"], labelKey: "web.base_editor.sc_fill_line" },
        { keys: ["Ctrl", "Shift", "Click"], labelKey: "web.base_editor.sc_fill_rect" },
        { keys: ["R"], labelKey: "web.base_editor.sc_rotate_ghost" },
        { keys: ["PageUp", "PageDown"], labelKey: "web.base_editor.sc_level_offset" },
        { keys: ["Shift", "PgUp/Dn"], labelKey: "web.base_editor.sc_stack_one" },
        { keys: ["Alt"], labelKey: "web.base_editor.sc_free_place" },
        { keys: ["Tab"], labelKey: "web.base_editor.sc_lock_anchor" },
      ],
    },
  ];
</script>

<!-- Backdrop -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  role="dialog"
  aria-modal="true"
  onclick={onclose}
  onkeydown={(e) => e.key === "Escape" && onclose()}
  tabindex="-1"
>
  <div
    class="card max-w-2xl w-full max-h-[80vh] overflow-y-auto"
    role="document"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.key === "Escape" && onclose()}
  >
    <div class="card-header flex items-center gap-2">
      <Icon icon="lucide:keyboard" width={16} class="text-accent-light" />
      <span>{$t("web.base_editor.shortcuts")}</span>
      <button type="button" class="ml-auto text-ink-dim hover:text-ink-secondary" onclick={onclose} title={$t("web.common.close")}>
        <Icon icon="lucide:x" width={16} />
      </button>
    </div>
    <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
      {#each groups as group (group.titleKey)}
        <div>
          <h4 class="text-xs font-semibold uppercase tracking-widest text-accent-light mb-2">
            {$t(group.titleKey)}
          </h4>
          <ul class="space-y-1">
            {#each group.items as item (item.labelKey)}
              <li class="flex items-center justify-between gap-3 text-xs">
                <span class="text-ink-secondary">{$t(item.labelKey)}</span>
                <span class="flex items-center gap-1 shrink-0">
                  {#each item.keys as k, i (k)}
                    {#if i > 0}<span class="text-ink-dim">+</span>{/if}
                    <kbd class="px-1.5 py-0.5 rounded-2 border border-line bg-bg-elevated text-[10px] font-mono text-ink-primary">{k}</kbd>
                  {/each}
                </span>
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    </div>
  </div>
</div>
