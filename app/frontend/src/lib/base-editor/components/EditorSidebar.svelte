<script lang="ts">
  // Right-hand panel — port of mappal's Sidebar.tsx + Palette.tsx. Uses PST V3
  // design tokens (Card, Badge, Icon, .input) and reads/writes the runes store.
  import Icon from "@iconify/svelte";
  import { t } from "$stores/index";
  import { editor, loadPlaceableTypes } from "../core/store.svelte";
  import {
    CATEGORY_COLOR,
    CATEGORY_LABEL,
    countByCategory,
    getTypeEntry,
    resolveType,
    unknownDimensionTypes,
  } from "../core/objectTypes";
  import { countOutsideRadius, findPalbox } from "../core/campGeometry";
  import { findDuplicateClusters } from "../core/overlapCheck";
  import { VERTICAL_PITCH } from "../core/types";

  const HEIGHT_LIMIT_TILES = 16;
  const HEIGHT_LIMIT_UNITS = HEIGHT_LIMIT_TILES * VERTICAL_PITCH;

  // Lazy-load the donor library on first palette render so the 3.4MB JSON
  // never lands in the main bundle.
  let placeableTypes: string[] = $state([]);
  let paletteOpen = $state(false);

  async function openPalette() {
    paletteOpen = !paletteOpen;
    if (paletteOpen && placeableTypes.length === 0) {
      placeableTypes = await loadPlaceableTypes();
    }
  }

  // Palette grouping (verbatim from the original Palette.tsx).
  type GroupKey = "Wood" | "Stone" | "Metal" | "SF" | "JapaneseStyle" | "Ancient" | "Production" | "Storage" | "Decor" | "Other";
  const GROUP_ORDER: GroupKey[] = ["Wood", "Stone", "Metal", "SF", "JapaneseStyle", "Ancient", "Production", "Storage", "Decor", "Other"];
  const GROUP_LABEL: Record<GroupKey, string> = {
    Wood: "Wood", Stone: "Stone", Metal: "Metal", SF: "SF",
    JapaneseStyle: "Japanese Style", Ancient: "Ancient",
    Production: "Production", Storage: "Storage", Decor: "Beds & Decor", Other: "Other",
  };

  function groupForType(typeId: string): GroupKey {
    const category = resolveType(typeId).category;
    if (category === "world") return "Other";
    const k = typeId.toLowerCase();
    if (k.startsWith("wood")) return "Wood";
    if (k.startsWith("stone")) return "Stone";
    if (k.startsWith("metal") || k.startsWith("iron")) return "Metal";
    if (k.startsWith("sf")) return "SF";
    if (k.startsWith("japanesestyle")) return "JapaneseStyle";
    if (k.startsWith("ancient")) return "Ancient";
    if (category === "production") return "Production";
    if (category === "storage") return "Storage";
    if (category === "decor") return "Decor";
    return "Other";
  }

  let search = $state("");
  let openSections = $state<Record<string, boolean>>({ Wood: true });
  const STORAGE_KEY = "pst.base-editor.palette.openSections";

  // Persist open-sections preference.
  $effect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(openSections));
    } catch {
      // best-effort
    }
  });

  // Load persisted open-sections once on mount.
  $effect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) openSections = { Wood: true, ...(JSON.parse(raw) as Record<string, boolean>) };
    } catch {
      // ignore
    }
  });

  let grouped = $derived.by(() => {
    const map = new Map<GroupKey, string[]>();
    for (const g of GROUP_ORDER) map.set(g, []);
    const q = search.trim().toLowerCase();
    const matches = (typeId: string): boolean => {
      if (!q) return true;
      const name = (getTypeEntry(typeId)?.name ?? typeId).toLowerCase();
      return name.includes(q) || typeId.toLowerCase().includes(q);
    };
    for (const typeId of placeableTypes) {
      if (!matches(typeId)) continue;
      map.get(groupForType(typeId))!.push(typeId);
    }
    return map;
  });

  // Selection-derived state.
  let selected = $derived(editor.selectedObjects);
  let typeBreakdown = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const o of selected) counts.set(o.typeId, (counts.get(o.typeId) ?? 0) + 1);
    return [...counts.entries()]
      .map(([typeId, count]) => ({ typeId, count, name: getTypeEntry(typeId)?.name ?? typeId }))
      .sort((a, b) => b.count - a.count);
  });

  // Guardrails.
  let palbox = $derived(findPalbox(editor.objects));
  let outsideRadius = $derived.by(() => {
    if (!editor.camp || !palbox.palbox) return 0;
    return countOutsideRadius(editor.objects, palbox.palbox.position, editor.camp.areaRange);
  });
  let aboveHeight = $derived.by(() => {
    if (!palbox.palbox) return 0;
    return editor.objects.reduce((n, o) => (o.position.z - palbox.palbox!.position.z > HEIGHT_LIMIT_UNITS ? n + 1 : n), 0);
  });
  let duplicateExtraIds = $derived(findDuplicateClusters(editor.objects).extraIds);

  let categoryCounts = $derived(countByCategory(editor.objects));
  let unknownDims = $derived(unknownDimensionTypes(editor.objects));

  // Inline-editable selection transform fields.
  const round = (n: number): number => Math.round(n);
</script>

<aside class="w-80 shrink-0 h-full overflow-y-auto border-l border-line/60 bg-bg-surface flex flex-col">
  <!-- Palette -->
  <div class="p-3 border-b border-line/40">
    <button type="button" class="w-full flex items-center gap-2 text-left" onclick={openPalette}>
      <Icon icon={paletteOpen ? "lucide:chevron-down" : "lucide:chevron-right"} width={14} class="text-ink-dim" />
      <Icon icon="lucide:package-plus" width={14} class="text-accent-light" />
      <span class="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
        {$t("web.base_editor.place_new")}
      </span>
      {#if placeableTypes.length > 0}
        <span class="ml-auto text-[10px] text-ink-dim">{placeableTypes.length}</span>
      {/if}
    </button>

    {#if paletteOpen}
      <p class="mt-2 text-[11px] text-ink-muted">
        {$t("web.base_editor.palette_hint")}
      </p>
      <input
        type="search"
        class="input mt-2 w-full text-xs"
        placeholder={placeableTypes.length ? $t("web.base_editor.search_n_types", { n: String(placeableTypes.length) }) : $t("web.base_editor.loading")}
        bind:value={search}
        onkeydown={(e) => {
          if (e.key !== "Escape") return;
          e.stopPropagation();
          if (search) { e.preventDefault(); search = ""; } else { (e.target as HTMLInputElement).blur(); }
        }}
      />

      {#if placeableTypes.length === 0}
        <p class="mt-2 text-[11px] text-ink-dim">{$t("web.base_editor.loading_donors")}</p>
      {/if}

      <div class="mt-2 space-y-1">
        {#each GROUP_ORDER as group (group)}
          {@const typeIds = grouped.get(group) ?? []}
          {#if typeIds.length > 0}
            {@const isOpen = search.trim().length > 0 || openSections[group]}
            <div>
              <button
                type="button"
                class="w-full flex items-center gap-1.5 text-left text-xs text-ink-secondary hover:text-ink-primary py-1"
                onclick={() => (openSections = { ...openSections, [group]: !openSections[group] })}
                disabled={search.trim().length > 0}
              >
                <span class="text-ink-dim">{isOpen ? "▾" : "▸"}</span>
                <span>{GROUP_LABEL[group]}</span>
                <span class="text-[10px] text-ink-dim">({typeIds.length})</span>
              </button>
              {#if isOpen}
                <div class="grid grid-cols-2 gap-1 mt-1">
                  {#each typeIds as typeId (typeId)}
                    {@const resolved = resolveType(typeId)}
                    {@const name = getTypeEntry(typeId)?.name ?? typeId}
                    {@const armed = editor.armedType === typeId}
                    <button
                      type="button"
                      class="flex items-center gap-1.5 px-1.5 py-1 rounded-4 text-[11px] border transition-fast text-left {armed ? 'border-accent bg-accent/15 text-accent-light' : 'border-line hover:border-line-hover text-ink-secondary'}"
                      title={armed ? $t("web.base_editor.disarm_hint") : $t("web.base_editor.place_hint", { name })}
                      aria-pressed={armed}
                      onclick={() => editor.toggleArm(typeId)}
                    >
                      <span class="w-2.5 h-2.5 rounded-2 shrink-0 border border-line" style="background: {resolved.color};"></span>
                      <span class="truncate">{name}</span>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        {/each}
      </div>

      {#if editor.armedType}
        <p class="mt-3 p-2 rounded-4 bg-accent/10 border border-accent/30 text-[11px] text-accent-light">
          {$t("web.base_editor.armed_hint", { name: getTypeEntry(editor.armedType)?.name ?? editor.armedType })}
        </p>
      {/if}
    {/if}
  </div>

  <!-- Category counts -->
  <div class="p-3 border-b border-line/40">
    <h3 class="text-xs font-semibold uppercase tracking-widest text-ink-secondary mb-2">
      {$t("web.base_editor.by_category")}
    </h3>
    <ul class="space-y-1">
      {#each categoryCounts as { category, count } (category)}
        <li class="flex items-center gap-2 text-xs">
          <span
            class="w-2.5 h-2.5 rounded-2 border border-line shrink-0"
            style="background: {category === "unknown" ? "#ff00ff" : CATEGORY_COLOR[category]};"
          ></span>
          <span class="flex-1 text-ink-secondary">
            {category === "unknown" ? $t("web.base_editor.unknown_type") : CATEGORY_LABEL[category]}
          </span>
          <span class="text-ink-muted tabular-nums">{count}</span>
        </li>
      {/each}
    </ul>
  </div>

  <!-- Selection -->
  <div class="p-3 border-b border-line/40">
    <h3 class="text-xs font-semibold uppercase tracking-widest text-ink-secondary mb-2">
      {$t("web.base_editor.selection")} ({selected.length})
    </h3>
    {#if selected.length === 0}
      <p class="text-[11px] text-ink-dim">{$t("web.base_editor.no_selection")}</p>
    {:else}
      <ul class="space-y-1 mb-2">
        {#each typeBreakdown.slice(0, 6) as { typeId, count, name } (typeId)}
          <li class="flex items-center gap-2 text-xs">
            <span class="flex-1 truncate text-ink-secondary">{name} ×{count}</span>
            <button
              type="button"
              class="text-[10px] text-accent-light hover:underline"
              onclick={() => editor.setSelection(editor.objects.filter((o) => o.typeId === typeId).map((o) => o.id))}
            >
              {$t("web.base_editor.all_of_type")}
            </button>
          </li>
        {/each}
        {#if typeBreakdown.length > 6}
          <li class="text-[10px] text-ink-dim">{$t("web.base_editor.and_n_more", { n: String(typeBreakdown.length - 6) })}</li>
        {/if}
      </ul>
      <ul class="space-y-1">
        {#each selected.slice(0, 8) as o (o.id)}
          <li class="text-[10px] font-mono text-ink-muted">
            <div class="text-ink-secondary">{o.typeId}</div>
            <div>
              ({round(o.position.x)}, {round(o.position.y)}, {round(o.position.z)})
              {#if typeof o.hpCurrent === "number" && typeof o.hpMax === "number"}
                · hp {o.hpCurrent}/{o.hpMax}
              {/if}
              {#if o.origin === "duplicate"} · dup{/if}
            </div>
          </li>
        {/each}
        {#if selected.length > 8}
          <li class="text-[10px] text-ink-dim">{$t("web.base_editor.and_n_more", { n: String(selected.length - 8) })}</li>
        {/if}
      </ul>
    {/if}
  </div>

  <!-- Guardrails -->
  <div class="p-3 border-b border-line/40">
    <h3 class="text-xs font-semibold uppercase tracking-widest text-ink-secondary mb-2">
      {$t("web.base_editor.guardrails")}
    </h3>
    {#if !editor.camp || !palbox.palbox}
      <p class="text-[11px] text-ink-dim">
        {$t("web.base_editor.guardrail_unavailable")}
      </p>
    {:else}
      <div class="space-y-1.5 text-xs">
        <div class="flex items-center gap-2 {outsideRadius > 0 ? 'text-status-warning' : 'text-ink-secondary'}">
          <span class="flex-1">{$t("web.base_editor.outside_radius")}</span>
          <span class="tabular-nums font-mono">{outsideRadius}</span>
        </div>
        <div class="flex items-center gap-2 {aboveHeight > 0 ? 'text-status-warning' : 'text-ink-secondary'}">
          <span class="flex-1">{$t("web.base_editor.above_height", { tiles: String(HEIGHT_LIMIT_TILES) })}</span>
          <span class="tabular-nums font-mono">{aboveHeight}</span>
        </div>
      </div>
    {/if}
    <div class="mt-2 pt-2 border-t border-line/40">
      <div class="flex items-center gap-2 {duplicateExtraIds.length > 0 ? 'text-status-warning' : 'text-ink-secondary'} text-xs">
        <span class="flex-1">{$t("web.base_editor.overlapping_dupes")}</span>
        <span class="tabular-nums font-mono">{duplicateExtraIds.length}</span>
      </div>
      {#if duplicateExtraIds.length > 0}
        <button
          type="button"
          class="mt-1 text-[10px] text-accent-light hover:underline"
          onclick={() => editor.setSelection(duplicateExtraIds)}
        >
          {$t("web.base_editor.select_duplicates")}
        </button>
      {/if}
    </div>
  </div>

  <!-- Warnings -->
  {#if editor.loadError || (editor.blueprint && editor.blueprint.warnings.length > 0) || unknownDims.length > 0}
    <div class="p-3 border-b border-line/40">
      <h3 class="text-xs font-semibold uppercase tracking-widest text-status-warning mb-2 flex items-center gap-1">
        <Icon icon="lucide:alert-triangle" width={12} />
        {$t("web.base_editor.warnings")}
      </h3>
      <ul class="space-y-1 text-[11px] text-ink-muted">
        {#if editor.loadError}<li class="text-status-error">{editor.loadError}</li>{/if}
        {#if editor.blueprint}
          {#each editor.blueprint.warnings as w (w)}<li>{w}</li>{/each}
        {/if}
        {#each unknownDims as u (u.typeId)}
          <li class="flex items-start gap-1.5">
            <span class="w-2 h-2 rounded-1 bg-fuchsia-500 shrink-0 mt-1"></span>
            <span>{u.typeId} × {u.count} — {u.registered ? $t("web.base_editor.no_dims") : $t("web.base_editor.not_in_registry")}</span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <!-- Credit (always visible at the bottom of the sidebar) -->
  <div class="mt-auto p-3 border-t border-line/40 text-[10px] text-ink-dim">
    {$t("web.base_editor.credit_prefix")}
    <a href="https://github.com/irehsrg" target="_blank" rel="noreferrer" class="text-accent-light hover:underline">@irehsrg</a>
    ·
    <a href="https://github.com/irehsrg/mappal-palworld" target="_blank" rel="noreferrer" class="text-accent-light hover:underline">mappal-palworld</a>
  </div>
</aside>
