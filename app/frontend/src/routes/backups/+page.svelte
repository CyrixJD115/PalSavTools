<script lang="ts">
  import { t } from '$stores/index';
  import ComingSoon from '$components/ui/ComingSoon.svelte';
</script>
<ComingSoon icon="lucide:archive" title={$t('web.coming_soon.backups_title')} description={$t('web.coming_soon.backups_desc')} phase={$t('web.coming_soon.phase_badge')} />
