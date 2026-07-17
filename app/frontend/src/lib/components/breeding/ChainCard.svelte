<script lang="ts">
  // Renders one breeding Chain: the header (target + generation count + gender
  // feasibility), the source pals (leaves), and the ordered breeding steps.
  // Steps are shown as a vertical list of [A] + [B] → [child] rows with the
  // passives inherited at each step. Source badges distinguish owned (from the
  // save), selected (user picks), and wild (catch one).
  import type { BreedablePal, Chain } from '$types/index';
  import Icon from '@iconify/svelte';
  import PalSlot from './PalSlot.svelte';

  let {
    chain,
    palMap,
  }: { chain: Chain; palMap: Map<string, BreedablePal> } = $props();

  const palFor = (tribe: string) => palMap.get(tribe);

  const sourceIcon = $derived({
    owned: { icon: 'lucide:package', label: 'Owned', cls: 'chip-blue' },
    selected: { icon: 'lucide:hand', label: 'Selected', cls: 'chip-green' },
    wild: { icon: 'lucide:trees', label: 'Wild', cls: 'chip-amber' },
  } as const);

  function srcMeta(type: string) {
    return sourceIcon[type as keyof typeof sourceIcon] ?? sourceIcon.selected;
  }

  // The matched passives are the required ones the chain actually delivers.
  const matchedSet = $derived(new Set(chain.matched_passives));
</script>

<div class="card space-y-3">
  <!-- header -->
  <div class="flex items-center justify-between gap-2 flex-wrap">
    <div class="flex items-center gap-2">
      <Icon icon="lucide:git-merge" width={16} class="text-accent" />
      <h3 class="text-sm font-semibold text-ink-emphasis">
        {palFor(chain.target)?.display_name ?? chain.target}
      </h3>
      <span class="chip text-[10px] px-2 py-0 chip-blue">{chain.generations} gen</span>
      {#if chain.gender_feasible}
        <Icon icon="lucide:check-circle-2" width={13} class="text-emerald-400" />
      {:else}
        <Icon icon="lucide:x-circle" width={13} class="text-rose-400" />
      {/if}
    </div>
    {#if chain.matched_passives.length}
      <div class="flex flex-wrap gap-1">
        {#each chain.matched_passives as passive}
          <span class="chip chip-green text-[9px] px-1.5 py-0">{passive}</span>
        {/each}
      </div>
    {/if}
  </div>

  <!-- sources (leaves) -->
  {#if chain.sources.length}
    <div class="flex flex-wrap gap-2">
      {#each chain.sources as src}
        {@const meta = srcMeta(src.type)}
        <div class="flex items-center gap-1.5 px-2 py-1 rounded-4 bg-bg-deep/50 border border-line/30">
          <PalSlot tribe={src.pal} display={src.display} icon={palFor(src.pal)?.icon} size="sm" gender={src.gender} />
          <span class="chip text-[8px] px-1 py-0 {meta.cls} shrink-0">
            <Icon icon={meta.icon} width={9} class="inline" />{meta.label}
          </span>
        </div>
      {/each}
    </div>
  {/if}

  <!-- steps -->
  {#if chain.steps.length}
    <div class="space-y-1.5">
      {#each chain.steps as step, i}
        <div class="flex items-center gap-2 p-2 rounded-4 bg-bg-deep/30 border border-line/20">
          <span class="text-[9px] text-ink-dim font-mono w-4 shrink-0">{i + 1}</span>
          <PalSlot tribe={step.parent_a} display={palFor(step.parent_a)?.display_name} icon={palFor(step.parent_a)?.icon} size="sm" />
          <Icon icon="lucide:plus" width={11} class="text-ink-dim shrink-0" />
          <PalSlot tribe={step.parent_b} display={palFor(step.parent_b)?.display_name} icon={palFor(step.parent_b)?.icon} size="sm" />
          <Icon icon="lucide:arrow-right" width={13} class="text-accent shrink-0" />
          <PalSlot tribe={step.child} display={palFor(step.child)?.display_name} icon={palFor(step.child)?.icon} size="sm" />
          {#if step.inherited_passives.length}
            <div class="flex flex-wrap gap-0.5 ml-auto shrink-0">
              {#each step.inherited_passives as p}
                <span class="chip text-[8px] px-1 py-0 {matchedSet.has(p) ? 'chip-green' : ''}">{p}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <p class="text-xs text-ink-dim italic">Target already available — no breeding required.</p>
  {/if}
</div>
