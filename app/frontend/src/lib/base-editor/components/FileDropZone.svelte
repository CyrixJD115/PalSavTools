<script lang="ts">
  // Drag-drop or file-picker for the base .json export. Mirrors mappal's
  // DropZone.tsx but uses PST V3 styling. Accepts a single .json file and
  // hands its text to editor.loadFile().
  import Icon from "@iconify/svelte";
  import { t } from "$stores/index";
  import { editor } from "../core/store.svelte";
  import { toast } from "$stores/toast";

  let dragging = $state(false);
  let fileInput: HTMLInputElement;

  function readAndLoad(file: File) {
    if (!/\.json$/i.test(file.name)) {
      toast.error($t("web.base_editor.err_not_json"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      editor.loadFile(file.name, text);
      if (editor.loadError) {
        toast.error(editor.loadError);
      } else {
        toast.success($t("web.base_editor.loaded", { name: file.name, count: String(editor.objects.length) }));
      }
    };
    reader.onerror = () => toast.error($t("web.base_editor.err_read_failed"));
    reader.readAsText(file);
  }

  function onDrop(e: DragEvent) {
    dragging = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) readAndLoad(file);
  }

  function onPick(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) readAndLoad(file);
    input.value = ""; // allow re-picking the same file
  }
</script>

<svelte:window ondragover={(e) => { e.preventDefault(); dragging = true; }} ondragleave={() => (dragging = false)} ondrop={onDrop} />

<div
  class="w-full max-w-xl mx-auto rounded-12 border-2 border-dashed p-10 text-center transition-fast {dragging ? 'border-accent bg-accent/10' : 'border-line-hover bg-bg-surface'}"
  role="button"
  tabindex="0"
  onkeydown={(e) => e.key === "Enter" && fileInput.click()}
  onclick={() => fileInput.click()}
>
  <Icon icon="lucide:upload-cloud" width={48} class="text-accent-light mx-auto mb-4" />
  <h2 class="text-lg font-semibold text-ink-primary mb-1">{$t("web.base_editor.drop_title")}</h2>
  <p class="text-sm text-ink-muted mb-4">{$t("web.base_editor.drop_hint")}</p>
  <p class="text-xs text-ink-dim">{$t("web.base_editor.drop_provenance")}</p>
  <input
    bind:this={fileInput}
    type="file"
    accept=".json,application/json"
    class="hidden"
    onchange={onPick}
  />
</div>
