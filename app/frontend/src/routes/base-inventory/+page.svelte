<script lang="ts">
  import { t } from '$stores/index';
  import ComingSoon from '$components/ui/ComingSoon.svelte';
</script>
<ComingSoon icon="lucide:warehouse" title={$t('web.coming_soon.base_inventory_title')} description={$t('web.coming_soon.base_inventory_desc')} phase={$t('web.coming_soon.phase_badge')} />
