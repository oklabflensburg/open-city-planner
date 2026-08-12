import { computed, onBeforeUnmount, onMounted, readonly, ref, shallowRef, type Ref } from 'vue'

type SaveResponse = { updated_at: string }
type SaveChanges = Record<string, unknown>
type SaveKind = 'public' | 'verwaltung'
type SaveJob = { kind: SaveKind, changes: SaveChanges }

export function usePolygonAutosave(options: {
  updatedAt: Ref<string>
  savePublic: (changes: SaveChanges) => Promise<SaveResponse>
  saveVerwaltung: (changes: SaveChanges) => Promise<SaveResponse>
  onSaved?: (kind: SaveKind, response: SaveResponse, changes: SaveChanges) => void | Promise<void>
  debounceMs?: number
}) {
  const status = ref<'saved' | 'dirty' | 'saving' | 'error' | 'conflict'>('saved')
  const pending: Record<SaveKind, SaveChanges> = { public: {}, verwaltung: {} }
  const failedJob = shallowRef<SaveJob | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false

  const isDirty = computed(() => status.value !== 'saved')

  function schedule(kind: SaveKind, changes: SaveChanges, immediate = false) {
    Object.assign(pending[kind], changes)
    status.value = 'dirty'
    failedJob.value = null
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => void flush(), immediate ? 0 : (options.debounceMs ?? 700))
  }

  async function flush() {
    if (running) return
    if (timer) clearTimeout(timer)
    timer = null
    running = true
    try {
      while (Object.keys(pending.public).length || Object.keys(pending.verwaltung).length) {
        const kind: SaveKind = Object.keys(pending.public).length ? 'public' : 'verwaltung'
        const changes = { ...pending[kind] }
        pending[kind] = {}
        status.value = 'saving'
        const save = kind === 'public' ? options.savePublic : options.saveVerwaltung
        try {
          const response = await save({ ...changes, expected_updated_at: options.updatedAt.value })
          options.updatedAt.value = response.updated_at
          await options.onSaved?.(kind, response, changes)
          failedJob.value = null
        } catch (error) {
          failedJob.value = { kind, changes }
          const statusCode = typeof error === 'object' && error && 'statusCode' in error
            ? Number(error.statusCode)
            : 0
          status.value = statusCode === 409 ? 'conflict' : 'error'
          break
        }
      }
      if (!failedJob.value && !Object.keys(pending.public).length && !Object.keys(pending.verwaltung).length) {
        status.value = 'saved'
      }
    } finally {
      running = false
      if (!failedJob.value && (Object.keys(pending.public).length || Object.keys(pending.verwaltung).length)) {
        void flush()
      }
    }
  }

  function retry() {
    const job = failedJob.value
    if (!job) return
    // Changes typed after the failed request are newer and must win on retry.
    pending[job.kind] = { ...job.changes, ...pending[job.kind] }
    failedJob.value = null
    void flush()
  }

  function beforeUnload(event: BeforeUnloadEvent) {
    if (!isDirty.value) return
    event.preventDefault()
  }

  if (typeof window !== 'undefined') {
    onMounted(() => window.addEventListener('beforeunload', beforeUnload))
    onBeforeUnmount(() => {
      window.removeEventListener('beforeunload', beforeUnload)
      if (timer) clearTimeout(timer)
    })
  }

  return {
    status: readonly(status),
    isDirty,
    schedulePublic: (changes: SaveChanges, immediate = false) => schedule('public', changes, immediate),
    scheduleVerwaltung: (changes: SaveChanges, immediate = false) => schedule('verwaltung', changes, immediate),
    flush,
    retry
  }
}
