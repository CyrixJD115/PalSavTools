<script lang="ts">
  // Export report modal — shows the notes/warnings reconcileExport() produced
  // (deletion tallies, linkage-lint issues, export-lint result). Port of
  // ExportNotesPanel.tsx as a modal so it matches PST's existing modal style.
  import Icon from "@iconify/svelte";
  import Button from "$components/ui/Button.svelte";
  import { t } from "$stores/index";

  let { notes, onclose }: { notes: string[]; onclose: () => void } = $props();

  // Split into clean vs warning notes for visual emphasis.
  let clean = $derived(notes.filter((n) => !n.startsWith("⚠")));
  let warnings = $derived(notes.filter((n) => n.startsWith("⚠")));
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  role="dialog"
  aria-modal="true"
  onclick={onclose}
  onkeydown={(e) => e.key === "Escape" && onclose()}
  tabindex="-1"
>
  <div class="card max-w-lg w-full" role="dialog" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && onclose()}>
    <div class="card-header flex items-center gap-2">
      <Icon icon="lucide:file-down" width={16} class="text-accent-light" />
      <span>{$t("web.base_editor.export_report")}</span>
      <button type="button" class="ml-auto text-ink-dim hover:text-ink-secondary" onclick={onclose} title={$t("web.common.close")}>
        <Icon icon="lucide:x" width={16} />
      </button>
    </div>
    <div class="p-4 space-y-3">
      {#if warnings.length > 0}
        <div class="p-2 rounded-4 border border-status-warning/40 bg-status-warning/10">
          <div class="flex items-center gap-1.5 text-status-warning text-xs font-semibold mb-1">
            <Icon icon="lucide:alert-triangle" width={12} />
            {$t("web.base_editor.warnings_count", { n: String(warnings.length) })}
          </div>
          <ul class="space-y-0.5 text-[11px] text-ink-muted">
            {#each warnings as w (w)}<li class="font-mono">{w}</li>{/each}
          </ul>
        </div>
      {/if}
      {#if clean.length > 0}
        <ul class="space-y-0.5 text-[11px] text-ink-muted font-mono">
          {#each clean as note (note)}<li>{note}</li>{/each}
        </ul>
      {/if}
      <div class="p-2 rounded-4 border border-line bg-bg-deep text-[11px] text-ink-dim">
        {$t("web.base_editor.import_reminder")}
      </div>
    </div>
    <div class="p-3 border-t border-line/40 flex justify-end">
      <Button variant="primary" onclick={onclose} class="h-8 px-3 text-xs">{$t("web.common.close")}</Button>
    </div>
  </div>
</div>
