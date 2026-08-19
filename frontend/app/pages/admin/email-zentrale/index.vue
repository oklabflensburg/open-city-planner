<script setup lang="ts">
definePageMeta({ middleware: 'superuser' })
await navigateTo('/admin/email-vorlagen', { replace: true })
</script>
