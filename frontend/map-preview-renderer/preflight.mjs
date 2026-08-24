import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import { validateStyle } from './rendering.mjs'

const [stylePath, expectedVersion, expectedIntegrity, releaseSha] = process.argv.slice(2)
if (!stylePath || !expectedVersion || !expectedIntegrity || !releaseSha) throw new Error('Usage: preflight.mjs STYLE VERSION INTEGRITY RELEASE_SHA')

const require = createRequire(import.meta.url)
const packageMetadata = require('@maplibre/maplibre-gl-native/package.json')
if (packageMetadata.version !== expectedVersion) throw new Error(`Expected MapLibre Native ${expectedVersion}, found ${packageMetadata.version}`)

const lockfile = await readFile(path.join(path.dirname(stylePath), '..', '..', 'pnpm-lock.yaml'), 'utf8')
const lockedPackage = `'@maplibre/maplibre-gl-native@${expectedVersion}':`
const packageOffset = lockfile.indexOf(lockedPackage)
const nextPackageOffset = packageOffset < 0 ? -1 : lockfile.indexOf("\n  '", packageOffset + lockedPackage.length)
const packageEntry = packageOffset < 0 ? '' : lockfile.slice(packageOffset, nextPackageOffset < 0 ? undefined : nextPackageOffset)
if (!packageEntry.includes(`integrity: ${expectedIntegrity}`)) throw new Error('Pinned MapLibre Native lockfile entry or integrity is missing')

const styleBytes = await readFile(stylePath)
validateStyle(JSON.parse(styleBytes.toString('utf8')))
require('@maplibre/maplibre-gl-native')
const nativeModulePath = path.join(path.dirname(require.resolve('@maplibre/maplibre-gl-native')), 'lib', `node-v${process.versions.modules}`, 'mbgl.node')

process.stdout.write(JSON.stringify({
  renderer: 'maplibre-native',
  rendererVersion: packageMetadata.version,
  releaseSha,
  styleHash: createHash('sha256').update(styleBytes).digest('hex'),
  nativeModulePath
}))
