<template>
  <Transition name="mobile-navigation">
    <div v-if="open" class="lg:hidden">
      <button class="fixed inset-0 top-16 z-[70] cursor-pointer bg-black/10" type="button" aria-label="Navigation schließen" @click="$emit('close')" />
      <nav :id="id" class="fixed inset-x-0 top-[var(--app-header-height)] z-[90] max-h-[calc(100dvh-var(--app-header-height))] overflow-y-auto overscroll-contain border-b border-slate-200 bg-white px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-[0_16px_34px_rgba(15,23,42,0.14)]" aria-label="Mobile Navigation">
        <p class="px-4 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">OK Lab Flensburg</p>
        <div class="grid gap-1">
          <NuxtLink
            v-for="item in primaryNavigation"
            :key="item.id"
            class="flex min-h-12 items-center rounded-xl px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="isActive(item) ? 'bg-[#edf4f8] text-slate-950' : ''"
            :aria-current="isActive(item) ? 'page' : undefined"
            :to="item.to"
            @click="$emit('close')"
          >
            {{ item.label }}
          </NuxtLink>
        </div>
        <div class="my-3 border-t border-[#eceeef]" />
        <div class="grid gap-1">
          <NuxtLink
            v-for="item in secondaryNavigation"
            :key="item.id"
            class="flex min-h-12 items-center rounded-xl px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]"
            :class="isActive(item) ? 'bg-slate-100 text-slate-950' : ''"
            :aria-current="isActive(item) ? 'page' : undefined"
            :to="item.to"
            @click="$emit('close')"
          >
            {{ item.label }}
          </NuxtLink>
        </div>
        <div class="my-3 border-t border-[#eceeef]" />
        <div v-if="authenticated" class="grid gap-1">
          <div class="mb-2 flex items-center gap-3 rounded-xl bg-[#f4f6f6] px-4 py-3">
            <UserAvatar :user="user" size="sm" loading="eager" />
            <div class="min-w-0">
              <p class="truncate text-sm font-bold text-[#202427]">{{ displayName }}</p>
              <p class="truncate text-xs text-[#687176]">{{ user?.email }}</p>
            </div>
          </div>
          <NuxtLink v-for="item in accountNavigation" :key="item.to" class="flex min-h-12 items-center rounded-xl px-4 text-sm font-semibold text-[#30363a] transition hover:bg-[#f4f6f6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :to="item.to" @click="$emit('close')">
            {{ item.label }}
          </NuxtLink>
          <button class="flex min-h-12 cursor-pointer items-center rounded-xl px-4 text-left text-sm font-semibold text-[#30363a] transition hover:bg-[#f4f6f6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" type="button" @click="$emit('logout')">
            Abmelden
          </button>
        </div>
        <div v-else class="grid gap-1">
          <NuxtLink class="flex min-h-12 items-center rounded-xl px-4 text-sm font-semibold text-[#30363a] transition hover:bg-[#f4f6f6] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/login" @click="$emit('close')">
            Anmelden
          </NuxtLink>
          <NuxtLink class="flex min-h-12 items-center rounded-xl bg-[#154d73] px-4 text-sm font-semibold text-white transition hover:bg-[#0f3f61] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/registrieren" @click="$emit('close')">
            Registrieren
          </NuxtLink>
        </div>
      </nav>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { AuthUser } from '~/types/auth'
import type { NavigationItem } from '~/composables/useSiteNavigation'

const route = useRoute()

defineProps<{
  id: string
  open: boolean
  primaryNavigation: NavigationItem[]
  secondaryNavigation: NavigationItem[]
  accountNavigation: NavigationItem[]
  authenticated: boolean
  user: AuthUser | null
  displayName: string
}>()

defineEmits<{
  close: []
  logout: []
}>()

function isActive(item: NavigationItem) {
  if (item.exact || item.to === '/') return route.path === item.to
  return route.path === item.to || route.path.startsWith(`${item.to}/`)
}
</script>
