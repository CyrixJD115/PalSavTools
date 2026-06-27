<script lang="ts">
  import { health } from '$stores/index';
  import Icon from '@iconify/svelte';

  let { open = $bindable(false) }: { open: boolean } = $props();

  let h = $derived($health);

  const features = [
    'Transfer saves between servers and co-op worlds',
    'Fix host saves and manage player/guild data',
    'Edit bases and manage save files',
    'Convert between Steam and GamePass formats',
    'Visualize and manage world maps',
  ];

  function close() { open = false; }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" role="presentation">
    <div class="w-full max-w-lg card shadow-card-lg border-accent/40 border-2" role="dialog" aria-modal="true" aria-label="About PST">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-ink-emphasis flex items-center gap-2">
          <Icon icon="lucide:info" width={18} class="text-accent" /> About PST
        </h2>
        <button class="text-ink-dim hover:text-ink-primary transition-fast" onclick={close} aria-label="Close">
          <Icon icon="lucide:x" width={18} />
        </button>
      </div>

      <div class="space-y-4">
        <div>
          <h3 class="text-lg font-bold heading-gradient">Palworld Save Tools v{h?.app_version ?? '?'}</h3>
          <p class="text-sm text-ink-secondary mt-1">
            A comprehensive toolkit for managing Palworld save files.
          </p>
        </div>

        <div>
          <p class="text-sm font-semibold text-ink-primary mb-2">Features:</p>
          <ul class="space-y-1.5">
            {#each features as f}
              <li class="flex items-start gap-2 text-sm text-ink-secondary">
                <Icon icon="lucide:check" width={14} class="text-accent mt-0.5 shrink-0" />
                <span>{f}</span>
              </li>
            {/each}
          </ul>
        </div>

        <div class="border-t border-line/40 pt-3 space-y-1 text-sm">
          <div class="flex items-center gap-2">
            <span class="text-ink-muted">Game Version:</span>
            <span class="text-ink-primary font-semibold">{h?.game_version ?? '?'}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-ink-muted">Developer:</span>
            <span class="text-ink-secondary">Palworld Save Tools Team</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-ink-muted">GitHub:</span>
            <a href="https://github.com/deafdudecomputers/PalworldSaveTools/releases/latest" target="_blank" rel="noreferrer"
               class="text-accent hover:text-accent-light underline underline-offset-2 transition-fast">
              View on GitHub
            </a>
          </div>
        </div>

        <p class="text-xs text-ink-dim border-t border-line/40 pt-3">© 2026 Palworld Save Tools</p>
      </div>

      <div class="flex justify-end mt-5">
        <button onclick={close} class="btn btn-primary">Close</button>
      </div>
    </div>
  </div>
{/if}
