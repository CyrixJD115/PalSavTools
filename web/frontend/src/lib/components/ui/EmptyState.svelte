<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from '@iconify/svelte';

  let {
    icon = 'lucide:inbox',
    title = 'Nothing here yet',
    class: klass = '',
    children,
  }: {
    icon?: string;
    title?: string;
    class?: string;
    children?: Snippet;
  } = $props();
</script>

<div class={klass}>
  <div class="flex flex-col items-center justify-center text-center py-12 px-4">
    <Icon icon={icon} width={32} class="text-ink-dim mb-3" />
    <p class="text-ink-secondary font-medium">{title}</p>
    {#if children}
      <div class="mt-2 text-sm text-ink-muted">{@render children()}</div>
    {/if}
  </div>
</div>
