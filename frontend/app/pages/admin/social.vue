<template>
  <ContentPageShell
    title="Social Publishing"
    description="Mastodon-Verbindung, ausstehende Gebietsupdates und Veröffentlichungshistorie prüfen."
    eyebrow="Administration"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Administration', to: '/admin/benutzer' }, { label: 'Social Publishing' }]"
    max-width="wide"
  >
    <template #badge><StatusBadge tone="warning">SUPERUSER</StatusBadge></template>

    <div v-if="loading && !mastodonStatus" class="grid gap-4 md:grid-cols-3" role="status" aria-label="Social Publishing wird geladen">
      <div v-for="index in 3" :key="index" class="h-36 animate-pulse rounded-2xl border border-slate-200 bg-white" />
    </div>
    <Card v-else-if="error && !mastodonStatus" class="border-rose-200 p-8 text-center">
      <CircleAlert class="mx-auto size-9 text-rose-600" aria-hidden="true" />
      <h2 class="mt-4 text-lg font-bold text-slate-950">Social Publishing konnte nicht geladen werden</h2>
      <p class="mt-2 text-sm text-rose-800" role="alert">{{ error }}</p>
      <Button class="mt-5" @click="load"><RefreshCw class="size-4" /> Erneut versuchen</Button>
    </Card>

    <template v-else-if="mastodonStatus">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(9rem,1fr))]">
        <Card class="p-5 sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500"><ProviderIcon provider="mastodon" class="size-5" /> Mastodon</p>
              <a :href="mastodonStatus.account_url" target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex items-center gap-2 font-bold text-[#154d73] underline underline-offset-4">
                {{ mastodonStatus.account }} <ExternalLink class="size-4" aria-hidden="true" />
              </a>
            </div>
            <StatusBadge :tone="connectionTone">{{ connectionLabel }}</StatusBadge>
          </div>
          <p class="mt-4 text-sm leading-6 text-slate-600">Automatische Gebietsupdates: <strong>{{ mastodonStatus.area_updates_enabled ? 'aktiv' : 'deaktiviert' }}</strong> · Sichtbarkeit: {{ mastodonStatus.visibility }}</p>
          <p class="mt-1 text-sm leading-6 text-slate-600">Letzte Veröffentlichung: <strong>{{ mastodonStatus.last_publication_at ? formatDate(mastodonStatus.last_publication_at) : 'Noch keine' }}</strong></p>
          <p v-if="mastodonStatus.dry_run" class="mt-2 text-sm font-semibold text-amber-800">Dry-Run aktiv: Es werden keine echten Statusmeldungen gesendet.</p>
          <p v-if="mastodonStatus.verification_error" class="mt-2 text-sm text-rose-800">{{ mastodonStatus.verification_error }}</p>
        </Card>
        <Card v-for="metric in metrics" :key="metric.label" class="p-5"><p class="text-sm font-semibold text-slate-600">{{ metric.label }}</p><p class="mt-2 text-3xl font-bold text-slate-950">{{ metric.value }}</p></Card>
      </div>

      <section v-if="settingsDraft" class="mt-8 min-w-0 space-y-6" aria-labelledby="social-settings-title">
        <div class="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0">
            <h2 id="social-settings-title" class="text-xl font-bold text-slate-950">Social-Publishing-Einstellungen</h2>
            <p class="mt-1 text-sm leading-6 text-slate-600">Änderungen werden automatisch gespeichert.</p>
          </div>
          <div class="flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold" role="status" aria-live="polite">
            <CircleAlert v-if="saveStatusKind === 'error'" class="size-4 shrink-0 text-rose-700" aria-hidden="true" />
            <LoaderCircle v-else-if="saveStatusKind === 'saving'" class="size-4 shrink-0 animate-spin text-[#154d73]" aria-hidden="true" />
            <CheckCircle2 v-else class="size-4 shrink-0 text-emerald-700" aria-hidden="true" />
            <span :class="saveStatusKind === 'error' ? 'text-rose-800' : saveStatusKind === 'saving' ? 'text-[#154d73]' : 'text-emerald-800'">{{ saveStatusLabel }}</span>
            <Button v-if="saveStatusKind === 'error' && !hashtagError" class="min-h-9 px-3" @click="retryAutosave">Erneut versuchen</Button>
          </div>
        </div>

        <div class="grid gap-6 xl:grid-cols-2">
          <Card class="p-5 sm:p-6">
            <div class="flex items-start justify-between gap-4">
              <div><h2 class="text-xl font-bold text-slate-950">Automatische Veröffentlichungen</h2><p class="mt-1 text-sm leading-6 text-slate-600">Beim Ausschalten bleibt die vorhandene Queue erhalten und wird pausiert.</p></div>
              <label class="inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-3"><span class="sr-only">Automatische Veröffentlichungen</span><input v-model="settingsDraft.enabled" type="checkbox" role="switch" :aria-checked="settingsDraft.enabled" class="size-5 accent-[#154d73]" @change="saveMasterSwitch"><span class="font-bold">{{ settingsDraft.enabled ? 'AN' : 'AUS' }}</span></label>
            </div>
            <fieldset class="mt-5"><legend class="field-label">Veröffentlichungsmodus</legend><div class="mt-2 grid gap-2">
              <label v-for="mode in approvalModes" :key="mode.value" class="flex min-h-11 min-w-0 cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 hover:bg-slate-50"><input v-model="settingsDraft.approval_mode" type="radio" :value="mode.value" class="mt-1 shrink-0 accent-[#154d73]" @change="scheduleControlPatch({ approval_mode: settingsDraft.approval_mode })"><span class="min-w-0"><strong class="block text-sm [overflow-wrap:anywhere]">{{ mode.label }}</strong><span class="text-xs text-slate-600 [overflow-wrap:anywhere]">{{ mode.description }}</span></span></label>
            </div></fieldset>
            <label class="mt-5 block min-w-0"><span class="field-label">Änderungen zusammenfassen</span><select v-model.number="settingsDraft.debounce_seconds" class="field-input" @change="scheduleControlPatch({ debounce_seconds: settingsDraft.debounce_seconds })"><option :value="0">Sofort</option><option :value="60">1 Minute</option><option :value="300">5 Minuten</option><option :value="900">15 Minuten</option><option :value="3600">1 Stunde</option></select></label>
          </Card>

          <Card class="p-5 sm:p-6">
            <h2 class="flex items-center gap-2 text-xl font-bold text-slate-950"><ProviderIcon provider="mastodon" class="size-6" /> Mastodon-Einstellungen</h2>
            <div class="mt-5 grid gap-4 sm:grid-cols-2">
              <label class="min-w-0"><span class="field-label">Sichtbarkeit</span><select v-model="settingsDraft.default_visibility" class="field-input" @change="scheduleControlPatch({ default_visibility: settingsDraft.default_visibility })"><option value="public">Öffentlich</option><option value="unlisted">Öffentlich, nicht gelistet</option><option value="private">Nur Follower</option></select></label>
              <label><span class="field-label">Sprache</span><input value="Deutsch (de)" disabled class="field-input bg-slate-100"></label>
            </div>
            <label class="mt-4 block min-w-0"><span class="field-label">Standard-Hashtags</span><input v-model="hashtagsInput" class="field-input" placeholder="Flensburg, OpenData, Stadtplaner" :aria-invalid="Boolean(hashtagError)" :aria-describedby="hashtagError ? 'social-hashtags-help social-hashtags-error' : 'social-hashtags-help'" @input="scheduleHashtagSave"><span id="social-hashtags-help" class="mt-1 block text-xs text-slate-500">Maximal fünf, ohne führendes #.</span><span v-if="hashtagError" id="social-hashtags-error" class="mt-1 block text-xs font-semibold text-rose-700">{{ hashtagError }}</span></label>
            <div class="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"><strong>Screenshots erforderlich</strong><p class="mt-1">Automatische Posts werden niemals ohne Bild und strukturierte Bildbeschreibung gesendet.</p></div>
          </Card>
        </div>

        <Card class="p-5 sm:p-6">
          <h2 class="text-xl font-bold text-slate-950">Automatisch veröffentlichte Themen</h2>
          <p class="mt-1 text-sm text-slate-600">Nur technisch implementierte, öffentliche Eventtypen stehen zur Auswahl. Neue Eventtypen bleiben standardmäßig deaktiviert.</p>
          <div class="mt-5 grid gap-6 lg:grid-cols-2">
            <fieldset v-for="group in topicGroups" :key="group.topic"><legend class="text-sm font-black uppercase tracking-wider text-[#154d73]">{{ group.label }}</legend><div class="mt-2 space-y-2">
              <label v-for="event in group.events" :key="event.event_type" class="flex min-h-11 min-w-0 cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 hover:bg-slate-50"><input :checked="settingsDraft.enabled_events.includes(event.event_type)" type="checkbox" class="mt-1 size-4 shrink-0 accent-[#154d73]" @change="toggleEvent(event.event_type)"><span class="min-w-0"><strong class="block text-sm text-slate-950 [overflow-wrap:anywhere]">{{ event.label }}</strong><span class="text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">{{ event.description }}</span></span></label>
            </div></fieldset>
          </div>
        </Card>

        <Card class="p-5 sm:p-6">
          <div class="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0">
              <h2 class="text-xl font-bold text-slate-950">Neue aus OSM übernommene Flächen</h2>
              <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Erzeugt genau beim erfolgreichen, bewussten OSM-Import einen einmaligen Post. Spätere Autosaves oder Bearbeitungen lösen keinen weiteren Post aus.</p>
            </div>
            <label class="inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-3">
              <span class="sr-only">Aus OpenStreetMap übernommene Flächen veröffentlichen</span>
              <input :checked="polygonAdoptionEnabled" type="checkbox" role="switch" :aria-checked="polygonAdoptionEnabled" aria-describedby="polygon-adoption-help" class="size-5 accent-[#154d73]" @change="togglePolygonAdoption">
              <span class="font-bold">{{ polygonAdoptionEnabled ? 'AN' : 'AUS' }}</span>
            </label>
          </div>
          <p id="polygon-adoption-help" class="sr-only">Veröffentlicht nur künftig bewusst in Stadtplaner übernommene OpenStreetMap-Flächen.</p>
          <label class="mt-5 block max-w-xl min-w-0"><span class="field-label">Ziel des Beitrags</span><select v-model="settingsDraft.polygon_osm_adoption_link_target" class="field-input disabled:cursor-not-allowed disabled:bg-slate-100" :disabled="!polygonAdoptionEnabled" aria-describedby="polygon-link-help" @change="scheduleControlPatch({ polygon_osm_adoption_link_target: settingsDraft.polygon_osm_adoption_link_target })"><option value="DETAIL_PAGE">Öffentliche Flächendetailseite</option><option value="GIS">GIS-Karte mit ausgewählter Fläche</option></select><span id="polygon-link-help" class="mt-1 block text-xs leading-5 text-slate-500">Der Pflicht-Screenshot verwendet denselben öffentlichen Zielkontext.</span></label>
        </Card>

        <Card class="p-5 sm:p-6">
          <h2 class="text-xl font-bold text-slate-950">Screenshot-Einstellungen</h2>
          <div class="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <label class="min-w-0"><span class="field-label">Format</span><select v-model="settingsDraft.screenshot_viewport" class="field-input" @change="scheduleControlPatch({ screenshot_viewport: settingsDraft.screenshot_viewport })"><option value="LANDSCAPE_16_9">1200 × 675 (16:9)</option><option value="LANDSCAPE_OG">1200 × 630</option><option value="SQUARE">1080 × 1080</option></select></label>
            <label v-for="option in screenshotOptions" :key="option.key" class="flex min-h-11 min-w-0 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 hover:bg-slate-50"><input v-model="settingsDraft[option.key]" type="checkbox" class="size-4 shrink-0 accent-[#154d73]" @change="saveScreenshotOption(option.key)"><span class="min-w-0 text-sm font-semibold [overflow-wrap:anywhere]">{{ option.label }}</span></label>
          </div>
          <p class="mt-4 text-xs leading-5 text-slate-500">Der Worker öffnet ausschließlich freigegebene öffentliche Stadtplaner-Routen ohne Anmeldung. Adminseiten und frei übergebene URLs sind technisch ausgeschlossen.</p>
        </Card>

      </section>

      <div class="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-950">Publication History</h2>
          <p class="mt-1 text-sm text-slate-600">{{ total }} Ereignisse · Tokens und Authorization-Header werden nie angezeigt.</p>
        </div>
        <label class="w-full sm:w-56"><span class="field-label">Status</span><select v-model="publicationStatus" class="field-input" @change="filterChanged"><option value="">Alle</option><option v-for="value in statuses" :key="value" :value="value">{{ statusLabel(value) }}</option></select></label>
      </div>

      <p v-if="error" class="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800" role="alert">{{ error }}</p>
      <div v-if="items.length" class="mt-4 space-y-3">
        <Card v-for="item in items" :key="item.id" class="p-5" :aria-busy="actingId === item.id">
          <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2"><StatusBadge :tone="statusTone(item.status)">{{ statusLabel(item.status) }}</StatusBadge><span class="text-xs font-semibold text-slate-500">{{ formatDate(item.created_at) }}</span></div>
              <h3 class="mt-3 font-bold text-slate-950">{{ item.resource_name }}</h3>
              <p class="mt-1 text-sm text-slate-600">{{ eventLabel(item.event_type) }}<template v-if="item.attempt_count > 0"> · {{ item.attempt_count }} {{ item.attempt_count === 1 ? 'Versuch' : 'Versuche' }}</template></p>
              <p v-if="item.event_type === 'POLYGON_ADOPTED_FROM_OSM'" class="mt-1 text-sm font-semibold text-[#154d73]">OpenStreetMap → Stadtplaner</p>
              <p v-if="item.changed_fields.length" class="mt-1 text-sm text-slate-600">Öffentliche Felder: {{ item.changed_fields.join(', ') }}</p>
              <p v-if="preparationHint(item)" class="mt-2 text-sm font-semibold text-[#154d73]" role="status">{{ preparationHint(item) }}</p>
              <p v-for="reason in item.blocking_reasons || []" :key="reason.code" class="mt-2 text-sm font-semibold text-amber-800">{{ reason.message }}</p>
              <p v-if="item.last_error" class="mt-2 text-sm text-rose-800">{{ item.last_error }}</p>
              <p v-if="actionErrors[item.id]" class="mt-2 text-sm font-semibold text-rose-800" role="alert">{{ actionErrors[item.id] }}</p>
            </div>
            <div class="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap" aria-label="Aktionen">
              <Button v-if="allows(item, 'PREVIEW')" @click="openPreview(item)"><Eye class="size-4" /> Vorschau</Button>
              <Button v-if="allows(item, 'APPROVE_AND_PUBLISH')" :disabled="actingId === item.id" @click="approveAndPublish(item)"><LoaderCircle v-if="actingId === item.id" class="size-4 animate-spin" /><Send v-else class="size-4" /> {{ actingId === item.id ? 'Wird veröffentlicht …' : 'Freigeben & veröffentlichen' }}</Button>
              <Button v-if="allows(item, 'DISCARD')" :disabled="actingId === item.id" @click="selectedCancel = item"><Ban class="size-4" /> Verwerfen</Button>
              <a v-if="allows(item, 'OPEN_REMOTE') && item.remote_url" :href="item.remote_url" target="_blank" rel="noopener noreferrer" class="page-button-secondary"><ProviderIcon provider="mastodon" class="size-4" /> Mastodon öffnen <ExternalLink class="size-4" aria-hidden="true" /></a>
              <NuxtLink v-if="allows(item, 'OPEN_RESOURCE') && item.resource_slug" class="page-button-secondary" :to="item.resource_type === 'USER_POLYGON' ? `/flaechen/${item.resource_slug}` : `/gebiete/${item.resource_slug}`">{{ item.resource_type === 'USER_POLYGON' ? 'Fläche' : 'Gebiet' }} öffnen</NuxtLink>
              <Button v-if="allows(item, 'RETRY')" @click="selectedRetry = item"><RotateCcw class="size-4" /> Erneut versuchen</Button>
            </div>
          </div>
        </Card>
      </div>
      <Card v-else class="mt-4 p-10 text-center"><Send class="mx-auto size-9 text-slate-400" /><h2 class="mt-4 text-lg font-bold text-slate-950">Keine Veröffentlichungen</h2><p class="mt-2 text-sm text-slate-600">Für den gewählten Status gibt es keine Ereignisse.</p></Card>

      <nav v-if="pages > 1" class="mt-6 flex items-center justify-between gap-3" aria-label="Seitennavigation">
        <Button :disabled="page <= 1 || loading" @click="changePage(page - 1)"><ChevronLeft class="size-4" /> Zurück</Button>
        <span class="text-sm font-semibold text-slate-600">Seite {{ page }} von {{ pages }}</span>
        <Button :disabled="page >= pages || loading" @click="changePage(page + 1)">Weiter <ChevronRight class="size-4" /></Button>
      </nav>
    </template>

    <AppConfirmDialog
      :open="Boolean(selectedRetry)"
      title="Veröffentlichung erneut versuchen?"
      body="Das fehlgeschlagene Ereignis wird wieder in die Outbox gestellt. Der Worker sendet es mit demselben stabilen Idempotency-Key."
      confirm-label="Erneut versuchen"
      :loading="Boolean(selectedRetry && retryingId === selectedRetry.id)"
      :error="retryError"
      @update:open="open => { if (!open) selectedRetry = null }"
      @cancel="selectedRetry = null"
      @confirm="confirmRetry"
    />
    <AppConfirmDialog :open="Boolean(selectedCancel)" title="Veröffentlichung verwerfen?" body="Das Ereignis wird abgebrochen und nicht automatisch veröffentlicht. Die Historie bleibt erhalten." confirm-label="Verwerfen" variant="danger" :loading="Boolean(selectedCancel && actingId === selectedCancel.id)" @update:open="open => { if (!open) selectedCancel = null }" @cancel="selectedCancel = null" @confirm="confirmCancel" />
    <AppModal :open="Boolean(previewData || previewLoading)" title="Mastodon Vorschau" description="Kontrollierter Text und Screenshot der öffentlichen Zielseite." size="lg" @update:open="closePreview">
      <div v-if="previewLoading" class="grid h-64 place-items-center"><LoaderCircle class="size-8 animate-spin text-[#154d73]" /></div>
      <div v-else-if="previewData" class="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
        <div><img v-if="previewData.screenshot_url" :src="previewImageUrl" crossorigin="use-credentials" :alt="previewData.alt_text" class="w-full rounded-xl border border-slate-200 bg-slate-100"><div v-else class="grid aspect-video place-items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600">Screenshot wird vom Publisher im Hintergrund vorbereitet.</div><p class="mt-3 text-sm"><strong>Bildbeschreibung:</strong> {{ previewData.alt_text }}</p></div>
        <div><p class="whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-800">{{ previewData.text }}</p><dl class="mt-4 space-y-2 text-sm"><div><dt class="font-bold">Eventtyp</dt><dd>{{ previewData.event_type }}</dd></div><div><dt class="font-bold">Ziel</dt><dd>{{ previewData.target_label }}</dd></div><div><dt class="font-bold">Ziel-URL</dt><dd class="break-all">{{ previewData.target_url }}</dd></div></dl><Button v-if="previewItem && allows(previewItem, 'APPROVE_AND_PUBLISH')" class="mt-6 w-full sm:w-auto" :disabled="actingId === previewItem.id" @click="approveFromPreview"><LoaderCircle v-if="actingId === previewItem.id" class="size-4 animate-spin" /><Send v-else class="size-4" /> Freigeben & veröffentlichen</Button></div>
      </div>
    </AppModal>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { Ban, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, ExternalLink, Eye, LoaderCircle, RefreshCw, RotateCcw, Send } from '@lucide/vue'
import type { SocialPublicationAction, SocialPublicationItem, SocialPublicationPreview, SocialPublicationStatus, SocialPublishingSettings, SocialPublishingSettingsPatch } from '~/types/admin'
import { buildApiUrl } from '~/utils/apiUrl'

definePageMeta({ middleware: 'social-publish' })

const {
  mastodonStatus, settings, items, total, pages, page, publicationStatus, loading, error,
  retryingId, savingSettings, settingsSaveStatus, settingsSaveError, actingId,
  load, retry, saveSettingsPatch, retrySettingsSave, flushSettingsSaves, preview, action
} = useSocialPublishing()
const selectedRetry = ref<SocialPublicationItem | null>(null)
const selectedCancel = ref<SocialPublicationItem | null>(null)
const retryError = ref('')
const actionErrors = reactive<Record<string, string>>({})
const settingsDraft = ref<SocialPublishingSettings | null>(null)
const hashtagsInput = ref('')
const hashtagError = ref('')
const controlSavePending = ref(false)
const hashtagSavePending = ref(false)
const previewData = ref<SocialPublicationPreview | null>(null)
const previewItem = ref<SocialPublicationItem | null>(null)
const previewLoading = ref(false)
const runtimeConfig = useRuntimeConfig()
const CONTROL_SAVE_DELAY_MS = 100
const TEXT_SAVE_DELAY_MS = 600
let controlSaveTimer: ReturnType<typeof setTimeout> | undefined
let hashtagSaveTimer: ReturnType<typeof setTimeout> | undefined
let publicationRefreshTimer: ReturnType<typeof setInterval> | undefined
let pendingControlPatch: SocialPublishingSettingsPatch = {}
let settingsInitialized = false
const statuses: SocialPublicationStatus[] = ['PENDING_APPROVAL', 'PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED', 'CANCELLED', 'DRY_RUN']
const approvalModes = [
  { value: 'AUTOMATIC', label: 'Automatisch veröffentlichen', description: 'Nach Debounce und Screenshot-Erzeugung direkt senden.' },
  { value: 'MANUAL', label: 'Vor Veröffentlichung freigeben', description: 'Screenshot und Text zunächst in der Warteschlange prüfen.' },
  { value: 'DRY_RUN', label: 'Nur Vorschau / Dry Run', description: 'Vollständig vorbereiten, aber nichts an Mastodon senden.' }
] as const
const screenshotOptions: Array<{ key: 'screenshot_show_map' | 'screenshot_show_facts' | 'screenshot_show_pois' | 'screenshot_show_branding', label: string }> = [
  { key: 'screenshot_show_map', label: 'Gebietskarte' }, { key: 'screenshot_show_facts', label: 'Kennzahlen' }, { key: 'screenshot_show_pois', label: 'POIs' }, { key: 'screenshot_show_branding', label: 'Branding' }
]
const topicGroups = computed(() => {
  const groups = new Map<string, { topic: string, label: string, events: SocialPublishingSettings['registry'] }>()
  for (const event of settingsDraft.value?.registry || []) {
    if (event.event_type === 'POLYGON_ADOPTED_FROM_OSM') continue
    const group = groups.get(event.topic) || { topic: event.topic, label: event.topic_label, events: [] }
    group.events.push(event)
    groups.set(event.topic, group)
  }
  return [...groups.values()]
})
const polygonAdoptionEnabled = computed(() => settingsDraft.value?.enabled_events.includes('POLYGON_ADOPTED_FROM_OSM') || false)
const previewImageUrl = computed(() => previewData.value?.screenshot_url ? buildApiUrl(runtimeConfig.public.apiBaseUrl, previewData.value.screenshot_url.replace(/^\/api\/v1/, '')) : '')
const metrics = computed(() => [
  { label: 'Offene Posts', value: mastodonStatus.value?.pending || 0 },
  { label: 'Fehlgeschlagen', value: mastodonStatus.value?.failed || 0 },
  { label: 'Veröffentlicht', value: mastodonStatus.value?.published || 0 }
])
const connectionLabel = computed(() => !mastodonStatus.value?.enabled ? 'Deaktiviert' : !mastodonStatus.value.configured ? 'Nicht konfiguriert' : mastodonStatus.value.reachable ? 'Verbunden' : 'Nicht erreichbar')
const connectionTone = computed(() => mastodonStatus.value?.reachable ? 'success' : mastodonStatus.value?.enabled ? 'danger' : 'neutral')
const saveStatusKind = computed(() => hashtagError.value || settingsSaveStatus.value === 'error'
  ? 'error'
  : savingSettings.value || controlSavePending.value || hashtagSavePending.value ? 'saving' : 'saved')
const saveStatusLabel = computed(() => {
  if (hashtagError.value) return 'Bitte Hashtags prüfen'
  if (settingsSaveStatus.value === 'error') return settingsSaveError.value || 'Änderungen konnten nicht gespeichert werden'
  if (saveStatusKind.value === 'saving') return 'Speichern …'
  return 'Gespeichert'
})

function statusLabel(value: SocialPublicationStatus) { return ({ PENDING_APPROVAL: 'Freigabe erforderlich', PENDING: 'Wird vorbereitet', PROCESSING: 'Wird veröffentlicht', PUBLISHED: 'Veröffentlicht', FAILED: 'Fehlgeschlagen', CANCELLED: 'Abgebrochen', DRY_RUN: 'Nur Vorschau (Dry Run)' })[value] }
function statusTone(value: SocialPublicationStatus) { return ({ PENDING_APPROVAL: 'warning', PENDING: 'warning', PROCESSING: 'info', PUBLISHED: 'success', FAILED: 'danger', CANCELLED: 'neutral', DRY_RUN: 'info' } as const)[value] }
function eventLabel(value: string) { return ({ AREA_CREATED: 'Gebiet erstellt', AREA_PUBLIC_DATA_UPDATED: 'Gebietsdaten aktualisiert', AREA_BOUNDARY_UPDATED: 'Gebietsgrenze aktualisiert', AREA_STATISTICS_UPDATED: 'Statistik aktualisiert', AREA_STATISTICS_BULK_UPDATED: 'Statistik-Sammelupdate', POLYGON_ADOPTED_FROM_OSM: 'Aus OSM übernommene Fläche' } as Record<string, string>)[value] || value }
function formatDate(value: string) { return new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function allows(item: SocialPublicationItem, actionName: SocialPublicationAction) {
  if (item.allowed_actions) return item.allowed_actions.includes(actionName)
  // Keep the admin usable during a rolling backend/frontend deployment.
  return actionName === 'PREVIEW' ? !item.remote_url && item.status !== 'CANCELLED'
    : actionName === 'APPROVE_AND_PUBLISH' ? item.status === 'PENDING_APPROVAL'
      : actionName === 'DISCARD' ? ['PENDING_APPROVAL', 'PENDING', 'FAILED'].includes(item.status)
        : actionName === 'OPEN_RESOURCE' ? Boolean(item.resource_slug)
          : actionName === 'OPEN_REMOTE' ? Boolean(item.remote_url)
            : actionName === 'RETRY' && item.status === 'FAILED'
}
function preparationHint(item: SocialPublicationItem) {
  if (item.status === 'PROCESSING') return 'Screenshot und Veröffentlichung werden verarbeitet …'
  if (item.status === 'PENDING') return item.screenshot_ready ? 'Zur Veröffentlichung eingeplant.' : 'Screenshot wird automatisch erstellt …'
  if (item.status === 'PENDING_APPROVAL' && !item.screenshot_ready && allows(item, 'APPROVE_AND_PUBLISH')) return 'Der Pflicht-Screenshot wird nach der Freigabe automatisch erstellt.'
  return ''
}
function filterChanged() { page.value = 1; void load() }
function changePage(value: number) { page.value = value; void load() }
async function confirmRetry() {
  if (!selectedRetry.value) return
  retryError.value = ''
  try { await retry(selectedRetry.value); selectedRetry.value = null } catch (caught) { retryError.value = caught instanceof Error ? caught.message : 'Das Ereignis konnte nicht erneut eingeplant werden.' }
}

function toggleEvent(eventType: string) {
  if (!settingsDraft.value) return
  const enabled = new Set(settingsDraft.value.enabled_events)
  enabled.has(eventType) ? enabled.delete(eventType) : enabled.add(eventType)
  settingsDraft.value.enabled_events = [...enabled]
  scheduleControlPatch({ enabled_events: [...settingsDraft.value.enabled_events] })
}

function togglePolygonAdoption() {
  toggleEvent('POLYGON_ADOPTED_FROM_OSM')
}

function saveMasterSwitch() {
  if (!settingsDraft.value) return
  saveSettingsPatch({ enabled: settingsDraft.value.enabled })
}

function scheduleControlPatch(patch: SocialPublishingSettingsPatch) {
  pendingControlPatch = { ...pendingControlPatch, ...patch }
  controlSavePending.value = true
  if (controlSaveTimer) clearTimeout(controlSaveTimer)
  controlSaveTimer = setTimeout(flushControlPatch, CONTROL_SAVE_DELAY_MS)
}

function flushControlPatch() {
  if (controlSaveTimer) clearTimeout(controlSaveTimer)
  controlSaveTimer = undefined
  if (Object.keys(pendingControlPatch).length) saveSettingsPatch(pendingControlPatch)
  pendingControlPatch = {}
  controlSavePending.value = false
}

function saveScreenshotOption(key: 'screenshot_show_map' | 'screenshot_show_facts' | 'screenshot_show_pois' | 'screenshot_show_branding') {
  if (!settingsDraft.value) return
  scheduleControlPatch({ [key]: settingsDraft.value[key] })
}

function parseHashtags(value: string) {
  const raw = value.split(',').map(item => item.trim().replace(/^#/, '')).filter(Boolean)
  if (raw.length > 5) return { tags: [] as string[], error: 'Bitte höchstens fünf Hashtags eingeben.' }
  const tags: string[] = []
  for (const tag of raw) {
    if (tag.length > 40) return { tags: [], error: 'Ein Hashtag darf höchstens 40 Zeichen lang sein.' }
    if (!/^[\p{L}\p{N}_]+$/u.test(tag)) return { tags: [], error: 'Hashtags dürfen nur Buchstaben, Zahlen und Unterstriche enthalten.' }
    if (!tags.includes(tag)) tags.push(tag)
  }
  return { tags, error: '' }
}

function scheduleHashtagSave() {
  if (hashtagSaveTimer) clearTimeout(hashtagSaveTimer)
  hashtagSaveTimer = undefined
  const parsed = parseHashtags(hashtagsInput.value)
  hashtagError.value = parsed.error
  hashtagSavePending.value = !parsed.error
  if (parsed.error) return
  if (settingsDraft.value) settingsDraft.value.default_hashtags = parsed.tags
  hashtagSaveTimer = setTimeout(flushHashtagSave, TEXT_SAVE_DELAY_MS)
}

function flushHashtagSave() {
  if (hashtagSaveTimer) clearTimeout(hashtagSaveTimer)
  hashtagSaveTimer = undefined
  hashtagSavePending.value = false
  const parsed = parseHashtags(hashtagsInput.value)
  hashtagError.value = parsed.error
  if (!parsed.error) saveSettingsPatch({ default_hashtags: parsed.tags })
}

function flushScheduledChanges() {
  if (controlSavePending.value) flushControlPatch()
  if (hashtagSavePending.value) flushHashtagSave()
}

function retryAutosave() {
  flushScheduledChanges()
  retrySettingsSave()
}
async function openPreview(item: SocialPublicationItem) {
  previewLoading.value = true
  try {
    previewItem.value = item
    previewData.value = await preview(item)
  } finally { previewLoading.value = false }
}
function closePreview(open: boolean) {
  if (open) return
  previewData.value = null
  previewItem.value = null
}
async function confirmCancel() {
  if (!selectedCancel.value) return
  await action(selectedCancel.value, 'cancel')
  selectedCancel.value = null
}
async function approveAndPublish(item: SocialPublicationItem, altText?: string) {
  delete actionErrors[item.id]
  try {
    await action(item, 'approve-and-publish', altText)
    if (previewItem.value?.id === item.id) {
      previewData.value = null
      previewItem.value = null
    }
  } catch (caught) {
    actionErrors[item.id] = caught instanceof Error ? caught.message : 'Veröffentlichung konnte nicht gestartet werden.'
  }
}
async function approveFromPreview() {
  if (!previewItem.value || !previewData.value) return
  await approveAndPublish(previewItem.value, previewData.value.alt_text)
}

onMounted(() => {
  void load()
  publicationRefreshTimer = setInterval(() => {
    if (!loading.value && items.value.some(item => ['PENDING', 'PROCESSING'].includes(item.status))) void load()
  }, 5000)
})
watch(settings, value => {
  if (!value || settingsInitialized) return
  settingsDraft.value = JSON.parse(JSON.stringify(value)) as SocialPublishingSettings
  hashtagsInput.value = value.default_hashtags.join(', ')
  settingsInitialized = true
}, { immediate: true })

onBeforeRouteLeave(async () => {
  flushScheduledChanges()
  if (settingsSaveStatus.value === 'error') retrySettingsSave()
  await flushSettingsSaves()
})

onBeforeUnmount(() => {
  flushScheduledChanges()
  if (publicationRefreshTimer) clearInterval(publicationRefreshTimer)
})

usePageSeo({ title: 'Social Publishing', description: 'Geschützte Mastodon-Verwaltung für Superuser.', path: '/admin/social', robots: 'noindex,nofollow', openGraph: false, twitter: false, structuredData: false })
</script>
