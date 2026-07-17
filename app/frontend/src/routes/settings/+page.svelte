<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { setStoredLang } from '$lib/i18n.svelte';
  import { health, languages, currentLang, i18n, isHealthy, t } from '$stores/index';
  import { toast } from '$stores/toast';
  import Card from '$components/ui/Card.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Icon from '@iconify/svelte';

  let switching = $state(false);

  async function switchLang(code: string) {
    if (code === $currentLang) return;
    switching = true;
    try {
      const res = await api.i18n(code);
      i18n.set(res.keys);
      currentLang.set(code);
      setStoredLang(code); // persist so it survives reload
      toast.success($t('web.toast.language_set', { code }));
    } catch {
      toast.error($t('web.toast.language_load_failed'));
    } finally {
      switching = false;
    }
  }

  onMount(async () => {
    if (!$languages) {
      try { languages.set(await api.languages()); } catch { /* ignore */ }
    }
    if (!$health) {
      try { health.set(await api.health()); } catch { /* ignore */ }
    }
  });
</script>

<div class="p-6 max-w-3xl mx-auto space-y-6 animate-fade-in">
  <div>
    <h1 class="text-xl font-bold heading-gradient">{$t('web.settings.title')}</h1>
    <p class="text-xs text-ink-muted">{$t('web.settings.subtitle')}</p>
  </div>

  <Card title={$t('web.settings.language')}>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {#each $languages?.available ?? [] as lang}
        <button
          class="relative p-3 rounded-6 border text-left transition-fast disabled:opacity-50
                 {lang.code === $currentLang
                   ? 'border-accent bg-accent/10 text-ink-primary shadow-glow'
                   : 'border-line bg-bg-deep text-ink-secondary hover:border-accent/40 hover:bg-bg-hover'}"
          onclick={() => switchLang(lang.code)}
          disabled={switching}
        >
          {#if lang.code === $currentLang}
            <Icon icon="lucide:check" width={14} class="absolute top-2 right-2 text-accent" />
          {/if}
          <p class="text-sm font-medium">{lang.label}</p>
          <p class="text-[10px] font-mono text-ink-muted mt-0.5">{lang.code}</p>
        </button>
      {/each}
    </div>
    <p class="mt-3 text-xs text-ink-muted flex items-center gap-1.5">
      <Icon icon="lucide:globe" width={12} /> {$t('web.settings.active')}
      <span class="text-ink-secondary font-mono">{$currentLang}</span>
    </p>
  </Card>

  <Card title={$t('web.settings.backend')}>
    <dl class="space-y-2 text-sm">
      <div class="flex justify-between py-1.5 border-b border-line/30">
        <dt class="text-ink-muted flex items-center gap-1.5"><Icon icon="lucide:cpu" width={13} /> {$t('web.settings.status')}</dt>
        <dd>
          {#if $isHealthy}
            <Badge tone="success">{$t('web.header.online').toLowerCase()}</Badge>
          {:else}
            <Badge tone="error">{$t('web.header.offline').toLowerCase()}</Badge>
          {/if}
        </dd>
      </div>
      <div class="flex justify-between py-1.5 border-b border-line/30">
        <dt class="text-ink-muted">{$t('web.settings.webui_version')}</dt>
        <dd class="text-ink-primary font-mono text-xs">{$health?.version ?? '—'}</dd>
      </div>
      <div class="flex justify-between py-1.5 border-b border-line/30">
        <dt class="text-ink-muted">{$t('web.settings.save_loaded')}</dt>
        <dd class="text-ink-secondary">{$health?.save_loaded ? $t('web.common.yes') : $t('web.common.no')}</dd>
      </div>
      <div class="flex justify-between py-1.5 border-b border-line/30">
        <dt class="text-ink-muted">{$t('web.settings.backend')}</dt>
        <dd class="text-ink-secondary text-xs">{$t('web.settings.backend_stack')}</dd>
      </div>
    </dl>
  </Card>

  <Card title={$t('web.settings.about')}>
    <p class="text-sm text-ink-secondary leading-relaxed">
      {$t('web.settings.about_text')}
    </p>
  </Card>
</div>
