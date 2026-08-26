export class MapRuntimeError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options)
    this.name = 'MapRuntimeError'
  }
}

export class DuplicateMapSourceError extends MapRuntimeError {
  constructor(id: string) {
    super(`Map source "${id}" is already registered.`)
    this.name = 'DuplicateMapSourceError'
  }
}

export class DuplicateMapLayerError extends MapRuntimeError {
  constructor(id: string) {
    super(`Map layer "${id}" is already registered.`)
    this.name = 'DuplicateMapLayerError'
  }
}

export class UnknownMapSourceError extends MapRuntimeError {
  constructor(sourceId: string, layerId: string) {
    super(`Map layer "${layerId}" references unknown source "${sourceId}".`)
    this.name = 'UnknownMapSourceError'
  }
}

export class MapRegistrySealedError extends MapRuntimeError {
  constructor(id: string) {
    super(`Map contribution "${id}" cannot be registered after bootstrap.`)
    this.name = 'MapRegistrySealedError'
  }
}

export class MapExtensionError extends MapRuntimeError {
  constructor(id: string, cause: unknown) {
    super(`Map extension "${id}" failed.`, { cause })
    this.name = 'MapExtensionError'
  }
}
