<template>
  <div class="min-h-screen bg-[var(--c-surface)] text-[var(--c-text)]">
    <AppHeader />
    <main class="min-h-screen pt-16">
      <slot />
    </main>
    <AppFooter />
  </div>
</template>
