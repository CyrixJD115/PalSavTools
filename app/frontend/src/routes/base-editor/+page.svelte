<script lang="ts">
  // Base Editor page — port of mappal-palworld's App.tsx + Header.tsx shell.
  //
  // Layout: a top toolbar (file name, undo/redo, mass-build tools, export,
  // shortcuts, credit) over a three-pane workspace:
  //   [LeftDock: Levels]   [Scene3D viewport]   [EditorSidebar]
  //
  // No <SaveGate> — this feature is file-based (user uploads a base .json
  // export, edits, downloads _edited.json) and works independently of the
  // loaded save.
  import { onMount, onDestroy } from "svelte";
  import Icon from "@iconify/svelte";
  import Card from "$components/ui/Card.svelte";
  import Button from "$components/ui/Button.svelte";
  import Badge from "$components/ui/Badge.svelte";
  import EmptyState from "$components/ui/EmptyState.svelte";
  import { t } from "$stores/index";
  import { editor } from "$lib/base-editor/core/store.svelte";
  import {
    startAutosave,
    markDirty,
    formatRelativeTime,
    autosaveStatus,
    autosaveLastSavedAt,
    restoreRecord,
    restoreBannerDismissed,
    dismissRestoreBanner,
    deleteAutosaveRecord,
  } from "$lib/base-editor/lib/autosave.svelte";
  import Scene3D from "$lib/base-editor/components/Scene3D.svelte";
  import EditorSidebar from "$lib/base-editor/components/EditorSidebar.svelte";
  import LeftDock from "$lib/base-editor/components/LeftDock.svelte";
  import FileDropZone from "$lib/base-editor/components/FileDropZone.svelte";
  import MassBuildPanels from "$lib/base-editor/components/MassBuildPanels.svelte";
  import ShortcutsModal from "$lib/base-editor/components/ShortcutsModal.svelte";
  import ExportNotesModal from "$lib/base-editor/components/ExportNotesModal.svelte";

  let openTool = $state<"circle" | "stack" | "relocate" | null>(null);
  let shortcutsOpen = $state(false);
  let exportNotes = $state<string[] | null>(null);
  let autosaveTick = $state(0);
  let stopAutosave: (() => void) | null = null;

  onMount(() => {
    stopAutosave = startAutosave({
      exportSnapshot: () => {
        const r = editor.exportBlueprint();
        return r ? { filename: r.filename, text: r.text } : null;
      },
      isLoaded: () => editor.isLoaded,
      undoCount: () => editor.undoStack.length,
    });
    // 1s tick so the "autosaved Ns ago" relative timestamp stays live.
    const tickId = setInterval(() => (autosaveTick++), 1000);
    return () => clearInterval(tickId);
  });

  onDestroy(() => {
    stopAutosave?.();
    stopAutosave = null;
  });

  // Track undo-stack length so the autosave loop can mark itself dirty. This
  // mirrors the original autosave.ts's subscribe-to-undoStack-length trick.
  let lastUndoLen = editor.undoStack.length;
  $effect(() => {
    const len = editor.undoStack.length;
    if (len !== lastUndoLen) {
      lastUndoLen = len;
      markDirty();
    }
  });

  function handleExport() {
    let result: ReturnType<typeof editor.exportBlueprint>;
    try {
      result = editor.exportBlueprint();
    } catch (err) {
      exportNotes = [
        "⚠ EXPORT FAILED — nothing was downloaded. Your edits are still in the editor.",
        err instanceof Error ? err.message : String(err),
        "Tip: Ctrl+Z past the last action often clears the state the export choked on.",
      ];
      return;
    }
    if (!result) return;
    const blob = new Blob([result.text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    exportNotes = result.notes;
  }

  function restoreSession() {
    const rec = restoreRecord.value;
    if (!rec) return;
    editor.loadFile(rec.fileName, rec.text);
    dismissRestoreBanner();
  }

  async function discardSession() {
    await deleteAutosaveRecord();
    dismissRestoreBanner();
  }

  let autosaveLabel = $derived.by(() => {
    void autosaveTick; // re-evaluate each tick
    if (autosaveStatus.value === "unavailable") return null;
    if (autosaveStatus.value === "idle" || autosaveLastSavedAt.value === null) return null;
    return formatRelativeTime(autosaveLastSavedAt.value);
  });
</script>

<div class="flex flex-col h-full min-h-0">
  <!-- Top toolbar -->
  <header class="shrink-0 flex items-center gap-3 px-4 h-12 border-b border-line/60 bg-bg-surface">
    <div class="flex items-center gap-2 min-w-0">
      <Icon icon="lucide:boxes" width={18} class="text-accent-light shrink-0" />
      <Badge tone="amber" class="shrink-0 text-[9px] uppercase tracking-wide">BETA</Badge>
      <span class="font-semibold text-sm text-ink-primary truncate">
        {editor.fileName ?? $t("web.base_editor.no_file")}
      </span>
      {#if editor.blueprint}
        <Badge tone="neutral" class="shrink-0">
          {editor.objects.length} {$t("web.base_editor.objects")}
        </Badge>
      {/if}
    </div>

    <div class="flex-1"></div>

    {#if editor.blueprint}
      <!-- Mass-build tools -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="px-2 h-8 rounded-6 text-xs border transition-fast {openTool === 'circle' ? 'border-accent bg-accent/15 text-accent-light' : 'border-line hover:border-line-hover text-ink-secondary'}"
          onclick={() => (openTool = openTool === "circle" ? null : "circle")}
          title={$t("web.base_editor.fill_circle_title")}
        >
          <Icon icon="lucide:circle-dot" width={14} class="inline -mt-0.5" /> {$t("web.base_editor.fill_circle")}
        </button>
        <button
          type="button"
          class="px-2 h-8 rounded-6 text-xs border transition-fast {openTool === 'stack' ? 'border-accent bg-accent/15 text-accent-light' : 'border-line hover:border-line-hover text-ink-secondary'}"
          onclick={() => (openTool = openTool === "stack" ? null : "stack")}
          title={$t("web.base_editor.vertical_stack_title")}
        >
          <Icon icon="lucide:layers" width={14} class="inline -mt-0.5" /> {$t("web.base_editor.vertical_stack")}
        </button>
        <button
          type="button"
          class="px-2 h-8 rounded-6 text-xs border transition-fast {openTool === 'relocate' ? 'border-accent bg-accent/15 text-accent-light' : 'border-line hover:border-line-hover text-ink-secondary'}"
          onclick={() => (openTool = openTool === "relocate" ? null : "relocate")}
          title={$t("web.base_editor.relocate_title")}
        >
          <Icon icon="lucide:move" width={14} class="inline -mt-0.5" /> {$t("web.base_editor.relocate")}
        </button>
      </div>

      <div class="w-px h-6 bg-line"></div>

      <Button variant="ghost" onclick={() => editor.setSelection(editor.objects.map((o) => o.id))} class="h-8 px-2 text-xs">
        <Icon icon="lucide:check-square" width={14} class="inline -mt-0.5 mr-1" />
        {$t("web.base_editor.select_all")}
      </Button>
      <Button variant="ghost" onclick={() => editor.undo()} disabled={editor.undoStack.length === 0} class="h-8 px-2 text-xs">
        ↶ <span class="ml-1 hidden sm:inline">{$t("web.base_editor.undo")}</span>
      </Button>
      <Button variant="ghost" onclick={() => editor.redo()} disabled={editor.redoStack.length === 0} class="h-8 px-2 text-xs">
        ↷ <span class="ml-1 hidden sm:inline">{$t("web.base_editor.redo")}</span>
      </Button>
      <Button variant="primary" onclick={handleExport} class="h-8 px-3 text-xs">
        <Icon icon="lucide:download" width={14} class="inline -mt-0.5 mr-1" />
        {$t("web.base_editor.export")}
      </Button>
      {#if autosaveLabel}
        <span class="text-[10px] text-ink-dim hidden md:inline">
          <Icon icon="lucide:save" width={10} class="inline" /> {$t("web.base_editor.autosaved")} {autosaveLabel}
        </span>
      {/if}
    {/if}

    <button
      type="button"
      class="w-8 h-8 rounded-6 border border-line text-ink-secondary hover:border-line-hover transition-fast"
      onclick={() => (shortcutsOpen = true)}
      title={$t("web.base_editor.shortcuts")}
    >
      <Icon icon="lucide:keyboard" width={14} class="inline" />
    </button>
    <a
      href="https://github.com/irehsrg/mappal-palworld/issues/new/choose"
      target="_blank"
      rel="noreferrer"
      class="hidden md:inline-flex items-center gap-1 px-2 h-8 rounded-6 border border-line text-ink-secondary hover:border-line-hover transition-fast text-xs"
      title={$t("web.base_editor.feedback_title")}
    >
      <Icon icon="lucide:message-circle" width={12} class="inline" />
      {$t("web.base_editor.feedback")}
    </a>
  </header>

  {#if openTool}
    <div class="shrink-0 px-4 py-2 border-b border-line/60 bg-bg-deep">
      <MassBuildPanels tool={openTool} onclose={() => (openTool = null)} />
    </div>
  {/if}

  <!-- Restore-session banner -->
  {#if restoreRecord.value && !restoreBannerDismissed.value && !editor.blueprint}
    <div class="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-status-amber/40 bg-status-amber/10 text-status-amber text-xs">
      <Icon icon="lucide:history" width={14} />
      <span>
        {$t("web.base_editor.restore_hint", { name: restoreRecord.value.fileName, count: String(restoreRecord.value.editCount) })}
      </span>
      <div class="flex-1"></div>
      <Button variant="secondary" class="h-7 px-2 text-xs" onclick={restoreSession}>
        {$t("web.base_editor.restore")}
      </Button>
      <Button variant="ghost" class="h-7 px-2 text-xs" onclick={discardSession}>
        {$t("web.base_editor.discard")}
      </Button>
    </div>
  {/if}

  <!-- Workspace -->
  <div class="flex-1 min-h-0 flex">
    {#if !editor.blueprint}
      <div class="flex-1 flex items-center justify-center p-6">
        <FileDropZone />
      </div>
      <!-- Recent-load error -->
      {#if editor.loadError}
        <div class="absolute bottom-4 left-1/2 -translate-x-1/2 max-w-md p-3 rounded-8 border border-status-error/50 bg-status-error/10 text-status-error text-xs">
          {editor.loadError}
        </div>
      {/if}
    {:else}
      <LeftDock />
      <div class="flex-1 min-w-0 relative">
        <Scene3D />
      </div>
      <EditorSidebar />
    {/if}
  </div>

  <!-- Credit footer (always visible) -->
  <footer class="shrink-0 px-4 py-1.5 border-t border-line/40 bg-bg-deep text-[10px] text-ink-dim flex items-center gap-2">
    <Icon icon="lucide:info" width={11} />
    <span>
      {$t("web.base_editor.credit_prefix")}
      <a
        href="https://github.com/irehsrg"
        target="_blank"
        rel="noreferrer"
        class="text-accent-light hover:underline"
      >@irehsrg</a>
      ·
      <a
        href="https://github.com/irehsrg/mappal-palworld"
        target="_blank"
        rel="noreferrer"
        class="text-accent-light hover:underline"
      >mappal-palworld</a>
      (MIT)
    </span>
    <div class="flex-1"></div>
    <span class="hidden md:inline">{$t("web.base_editor.workflow_hint")}</span>
  </footer>
</div>

{#if shortcutsOpen}
  <ShortcutsModal onclose={() => (shortcutsOpen = false)} />
{/if}
{#if exportNotes}
  <ExportNotesModal notes={exportNotes} onclose={() => (exportNotes = null)} />
{/if}
