<script lang="ts">
  import { onMount } from 'svelte'
  import { isTauri } from '$lib/tauri'
  import { t } from '$stores/index'
  import Icon from '@iconify/svelte'

  let {
    onFilesDrop,
    children,
  }: {
    onFilesDrop: (paths: string[]) => void
    children?: import('svelte').Snippet
  } = $props()

  let dragOver = $state(false)
  let cleanup: (() => void) | null = null

  $effect(() => {
    if (!isTauri()) return

    import('@tauri-apps/api/window').then(({ getCurrentWindow }) => {
      const unlisten = getCurrentWindow().onDragDropEvent((ev) => {
        if (ev.payload.type === 'over') {
          dragOver = true
        } else if (ev.payload.type === 'leave') {
          dragOver = false
        } else if (ev.payload.type === 'drop') {
          dragOver = false
          onFilesDrop(ev.payload.paths)
        }
      })
      return unlisten
    }).then((fn) => { cleanup = fn })
  })

  onMount(() => () => { cleanup?.() })
</script>

{#if dragOver}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg-base/90 backdrop-blur-sm">
    <div class="w-60 h-60 rounded-2xl border-2 border-dashed border-status-success/60 flex flex-col items-center justify-center gap-2 bg-bg-elevated/80">
      <Icon icon="lucide:upload" width={40} class="text-status-success" />
      <span class="text-base font-bold text-status-success">{$t('web.overview.drop_level_sav')}</span>
      <span class="text-xs text-ink-muted">{$t('web.overview.drop_load_save')}</span>
    </div>
  </div>
{/if}

{#if children}{@render children()}{/if}
