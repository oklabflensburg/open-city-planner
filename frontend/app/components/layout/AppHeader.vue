<template>
  <header class="fixed inset-x-0 top-0 z-[80] w-full border-b border-slate-200/70 bg-white/95 shadow-[0_1px_3px_rgba(15,23,42,0.06)] backdrop-blur">
    <div class="mx-auto flex h-[var(--app-header-height)] w-full max-w-[1920px] items-center justify-between px-4 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">
      <div class="flex min-w-0 items-center gap-8 lg:gap-10">
        <NuxtLink class="group flex min-h-11 shrink-0 items-center rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#154d73]" to="/" @click="closeMenu">
          <OKLabLogo size="compact" />
        </NuxtLink>

        <nav class="hidden items-center gap-1 lg:flex" aria-label="Hauptnavigation">
          <NuxtLink
            v-for="item in primaryNavigation"
            :key="item.id"
            class="rounded-lg px-3.5 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="isActive(item) ? 'bg-[#edf4f8] text-slate-950' : ''"
            :aria-current="isActive(item) ? 'page' : undefined"
            :to="item.to"
          >
            {{ item.label }}
          </NuxtLink>
        </nav>
      </div>

      <div class="hidden min-w-0 items-center gap-3 lg:flex">
        <UiContributionSlot slot="header.actions" class="flex items-center gap-2" />
        <nav class="hidden items-center gap-1 min-[1400px]:flex" aria-label="Rechtliche Navigation">
          <NuxtLink
            v-for="item in legalNavigation"
            :key="item.id"
            class="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="isActive(item) ? 'bg-slate-100 text-slate-950' : ''"
            :aria-current="isActive(item) ? 'page' : undefined"
            :to="item.to"
          >
            {{ item.label }}
          </NuxtLink>
        </nav>

        <ClientOnly>
          <template v-if="authStore.authenticated">
            <LazyNotificationBell data-header-notifications mode="desktop" />
            <NuxtLink
              v-if="route.path === '/karte'"
              data-header-create-cta
              class="inline-flex h-11 w-auto shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-[#154d73] bg-white px-4 text-sm font-bold text-[#154d73] transition-colors hover:bg-[#edf4f8] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
              to="/flaechen/neu"
              aria-label="Neue Fläche anlegen"
            >
              <Plus class="size-5 shrink-0" aria-hidden="true" />
              <span class="whitespace-nowrap">Neue Fläche</span>
            </NuxtLink>
            <div class="relative min-w-0 max-w-[180px] xl:max-w-[220px] 2xl:max-w-[260px]">
              <button
                ref="accountButton"
                data-header-account
            class="inline-flex h-10 w-full min-w-0 cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
                type="button"
                :aria-expanded="accountOpen"
                aria-haspopup="menu"
                @click="accountOpen = !accountOpen"
              >
                <UserAvatar :user="authStore.user" size="sm" loading="eager" />
                <span class="truncate">{{ authStore.displayName }}</span>
                <ChevronDown class="size-4 shrink-0" />
              </button>
              <div v-if="accountOpen" ref="accountMenu" class="absolute right-0 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_16px_34px_rgba(15,23,42,0.14)]" role="menu">
                <div class="flex items-center gap-3 border-b border-[#eceeef] px-3 py-3">
                  <UserAvatar :user="authStore.user" size="sm" loading="eager" />
                  <div class="min-w-0">
                    <p class="truncate text-sm font-bold text-[#202427]">{{ authStore.displayName }}</p>
                    <p class="truncate text-xs text-[#687176]">{{ authStore.user?.email }}</p>
                  </div>
                </div>
                <NuxtLink v-for="item in accountNavigation" :key="item.to" class="flex min-h-10 items-center rounded-lg px-3 text-sm font-semibold text-[#30363a] hover:bg-[#f4f6f6]" :to="item.to" role="menuitem" @click="accountOpen = false">
                  {{ item.label }}
                </NuxtLink>
                <button data-account-logout class="flex min-h-10 w-full cursor-pointer items-center rounded-lg px-3 text-left text-sm font-semibold text-[#30363a] hover:bg-[#f4f6f6]" type="button" role="menuitem" @click="logout">
                  Abmelden
                </button>
              </div>
            </div>
          </template>
          <template v-else>
            <NuxtLink class="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/login">
              Anmelden
            </NuxtLink>
            <NuxtLink class="rounded-lg bg-[#154d73] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/registrieren">
              Registrieren
            </NuxtLink>
          </template>
          <template #fallback>
            <span class="h-11 w-[min(24rem,40vw)] shrink-0 rounded-xl bg-slate-100" aria-hidden="true" />
          </template>
        </ClientOnly>
      </div>

      <div class="flex items-center gap-1 lg:hidden">
        <ClientOnly>
          <LazyNotificationBell v-if="authStore.authenticated" mode="mobile" />
          <template #fallback>
            <span class="size-11 shrink-0" aria-hidden="true" />
          </template>
        </ClientOnly>
        <button
          class="inline-flex size-11 cursor-pointer items-center justify-center rounded-xl text-[#30363a] transition hover:bg-[#f4f6f6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
          type="button"
          aria-controls="mobile-navigation"
          :aria-expanded="mobileOpen"
          :aria-label="mobileOpen ? 'Navigation schließen' : 'Navigation öffnen'"
          @click="toggleMenu"
        >
          <X v-if="mobileOpen" class="size-5" />
          <Menu v-else class="size-5" />
        </button>
      </div>
    </div>

    <MobileNavigation
      id="mobile-navigation"
      :open="mobileOpen"
      :primary-navigation="primaryNavigation"
      :secondary-navigation="legalNavigation"
      :account-navigation="accountNavigation"
      :authenticated="authStore.authenticated"
      :user="authStore.user"
      :display-name="authStore.displayName"
      @close="closeMenu"
      @logout="logout"
    />
  </header>
</template>

<script setup lang="ts">
import { ChevronDown, Menu, Plus, X } from '@lucide/vue'
import { hasVerwaltungRole } from '~/utils/roles'
import { hasPermissionSnapshot } from '~/utils/permissions'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const mobileOpen = ref(false)
const accountOpen = ref(false)
const accountButton = ref<HTMLElement | null>(null)
const accountMenu = ref<HTMLElement | null>(null)
const { primaryNavigation, legalNavigation, userNavigation, adminNavigation } = useSiteNavigation()
const accountNavigation = computed(() => sortNavigationItems([...composeNavigation([
  { label: 'Profil', to: '/profil' },
  { label: 'Meine Flächen', to: '/meine-flaechen' },
  { label: 'Sicherheit', to: '/profil/sicherheit' },
  ...(hasVerwaltungRole(authStore.user) ? [{ label: 'Kennzahlen verwalten', to: '/verwaltung/kennzahlen' }] : []),
  ...(authStore.user?.is_superuser ? [{ label: 'Administration', to: '/admin/benutzer' }, { label: 'E-Mail-Zentrale', to: '/admin/email-vorlagen' }, { label: 'Auditlog', to: '/admin/audit-log' }] : []),
]), ...userNavigation.value, ...adminNavigation.value]))

function isActive(item: { to: string, exact?: boolean }) {
  const path = item.to
  if (item.exact || path === '/') return route.path === path
  return route.path === path || route.path.startsWith(`${path}/`)
}
function toggleMenu() {
  mobileOpen.value = !mobileOpen.value
}

function closeMenu() {
  mobileOpen.value = false
  accountOpen.value = false
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeMenu()
  }
}

function handleClick(event: MouseEvent) {
  const target = event.target as Node
  if (accountOpen.value && !accountButton.value?.contains(target) && !accountMenu.value?.contains(target)) {
    accountOpen.value = false
  }
}

async function logout() {
  closeMenu()
  await authStore.logout()
  await router.push('/login')
}

watch(() => route.fullPath, closeMenu)

watch(mobileOpen, (open) => {
  if (!import.meta.client) return
  document.body.classList.toggle('mobile-nav-open', open)
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('click', handleClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('click', handleClick)
  if (import.meta.client) {
    document.body.classList.remove('mobile-nav-open')
  }
})
</script>
