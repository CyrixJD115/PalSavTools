<script lang="ts">
  import { t } from '$stores/index';
  import ComingSoon from '$components/ui/ComingSoon.svelte';
</script>
<ComingSoon icon="lucide:shield-off" title={$t('web.coming_soon.exclusions_title')} description={$t('web.coming_soon.exclusions_desc')} phase={$t('web.coming_soon.phase_badge')} />
