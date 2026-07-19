<script lang="ts">
  import { untrack } from 'svelte';
  import Icon from '@iconify/svelte';
  import { t, loadProgress } from '$stores/index';

  let { open = false, onCancel }: { open: boolean; onCancel?: () => void } = $props();

  // When the backend broadcasts load_progress stages, swap the indeterminate
  // bar for a real progress bar + the section name. Falls back to the
  // indeterminate rotating-phrase path when no progress is available.
  const hasProgress = $derived(!!$loadProgress && $loadProgress!.stage !== 'done');
  const pct = $derived(
    $loadProgress && $loadProgress!.total > 0
      ? Math.min(100, Math.round(($loadProgress!.current / $loadProgress!.total) * 100))
      : 0,
  );
  const stageLabel = $derived(
    $loadProgress ? stageToLabel($loadProgress!.stage) : '',
  );

  function stageToLabel(stage: string): string {
    switch (stage) {
      case 'parse': return $t('web.loading.stage_parse');
      case 'precompute': return $t('web.loading.stage_precompute');
      case 'prewarm': return $t('web.loading.stage_prewarm');
      default: return '';
    }
  }

  const phrases = [
    'web.loading.phrase_1',
    'web.loading.phrase_2',
    'web.loading.phrase_3',
    'web.loading.phrase_4',
    'web.loading.phrase_5',
    'web.loading.phrase_6',
    'web.loading.phrase_7',
    'web.loading.phrase_8',
    'web.loading.phrase_9',
    'web.loading.phrase_10',
    'web.loading.phrase_11',
    'web.loading.phrase_12',
    'web.loading.phrase_13',
    'web.loading.phrase_14',
    'web.loading.phrase_15',
    'web.loading.phrase_16',
    'web.loading.phrase_17',
    'web.loading.phrase_18',
    'web.loading.phrase_19',
    'web.loading.phrase_20',
  ];

  let phraseIdx = $state(0);
  let seconds = $state(0);
  let fading = $state(false);

  let tick: ReturnType<typeof setInterval> | undefined;
  let cycle: ReturnType<typeof setInterval> | undefined;

  function stop() {
    if (tick !== undefined) { clearInterval(tick); tick = undefined; }
    if (cycle !== undefined) { clearInterval(cycle); cycle = undefined; }
  }

  $effect(() => {
    if (open) {
      untrack(() => {
        seconds = 0;
        phraseIdx = Math.floor(Math.random() * phrases.length);
        tick = setInterval(() => seconds++, 1000);
        cycle = setInterval(() => {
          fading = true;
          setTimeout(() => {
            phraseIdx = (phraseIdx + 1) % phrases.length;
            fading = false;
          }, 350);
        }, 3000);
      });
    } else {
      stop();
    }
    return stop;
  });

  function fmtTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open && onCancel) onCancel();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
    role="dialog" aria-modal="true">
    <div class="w-[420px] rounded-2xl bg-[rgba(18,20,24,0.95)] border border-accent/10 shadow-2xl animate-slide-up">
      <div class="flex flex-col items-center gap-4 px-10 py-8">
        <Icon icon="eos-icons:loading" width={40} class="text-accent" />

        {#if hasProgress}
          <div class="w-full">
            <div class="flex items-center justify-between text-[10px] text-ink-muted mb-1 tabular-nums">
              <span>{stageLabel}</span>
              <span>{pct}%</span>
            </div>
            <div class="w-full h-1.5 rounded-full overflow-hidden bg-white/5">
              <div class="h-full rounded-full bg-gradient-to-r from-sky-400 to-violet-500 transition-all duration-300"
                style="width: {pct}%"></div>
            </div>
            {#if $loadProgress?.section}
              <p class="text-[10px] text-ink-dim/60 font-mono mt-1.5 truncate text-center">
                {$loadProgress!.section}
              </p>
            {/if}
          </div>
        {:else}
          <div class="w-full h-1 rounded-full overflow-hidden bg-white/5">
            <div class="h-full w-1/3 rounded-full bg-gradient-to-r from-sky-400 to-violet-500 animate-loading-bar"></div>
          </div>
        {/if}

        <p class="text-sm font-semibold text-ink-emphasis text-center h-10 flex items-center justify-center leading-snug transition-opacity duration-300"
          class:opacity-0={fading && !hasProgress}>
          {#if hasProgress && $loadProgress?.stage === 'prewarm'}
            {$t('web.loading.prewarming', { current: String($loadProgress!.current), total: String($loadProgress!.total) })}
          {:else}
            {$t(phrases[phraseIdx])}
          {/if}
        </p>

        <p class="text-xs text-ink-dim/40 tabular-nums">{fmtTime(seconds)}</p>

        {#if onCancel}
          <button
            onclick={onCancel}
            class="text-xs text-ink-dim/60 hover:text-ink-secondary transition-colors px-3 py-1 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06]"
          >
            {$t('web.loading.escape_cancel')}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}
