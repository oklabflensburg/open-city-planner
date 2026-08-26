import type { MapTelemetry as MapTelemetryContract } from '#frontend-module-sdk'

export interface MapTelemetryEntry {
  readonly name: string
  readonly durationMs: number
}

export class MapTelemetry implements MapTelemetryContract {
  readonly #entries: MapTelemetryEntry[] = []
  readonly #report?: (entry: MapTelemetryEntry) => void

  constructor(report?: (entry: MapTelemetryEntry) => void) {
    this.#report = report
  }

  async measure<T>(name: string, operation: () => T | Promise<T>): Promise<T> {
    const started = performance.now()
    try {
      return await operation()
    } finally {
      this.record(name, performance.now() - started)
    }
  }

  record(name: string, durationMs: number) {
    const entry = Object.freeze({ name, durationMs })
    this.#entries.push(entry)
    this.#report?.(entry)
  }

  snapshot() {
    return Object.freeze([...this.#entries])
  }
}
