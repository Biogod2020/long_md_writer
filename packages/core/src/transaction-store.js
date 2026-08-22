import { createHash, randomUUID } from 'node:crypto'
import {
  appendFile,
  mkdir,
  open,
  readFile,
  rename,
  rm,
  stat,
  unlink,
  writeFile,
} from 'node:fs/promises'
import { hostname } from 'node:os'
import path from 'node:path'

export const RUNTIME_DIRECTORY = '.longwriter'
export const RUNTIME_STATE_FILENAME = 'state.json'
export const OPERATIONS_FILENAME = 'operations.jsonl'
export const REVIEWS_DIRECTORY = 'reviews'

const STATE_SCHEMA_VERSION = 1
const DEFAULT_LOCK_TIMEOUT_MS = 30_000
const DEFAULT_STALE_LOCK_MS = 120_000
const LOCK_HEARTBEAT_MS = 15_000

function resolveWorkspace(workspace) {
  if (typeof workspace !== 'string' || workspace.trim().length === 0) {
    throw new TypeError('workspace must be a non-empty path')
  }
  return path.resolve(workspace)
}

function runtimePath(workspace, ...segments) {
  return path.join(resolveWorkspace(workspace), RUNTIME_DIRECTORY, ...segments)
}

function publicRuntimeState(state) {
  return {
    schema_version: state.schema_version,
    revision: state.revision,
    snapshot_sha256: state.snapshot_sha256,
    finalized: state.finalized,
    finalized_at: state.finalized_at ?? null,
    review_receipts: Array.isArray(state.review_receipts) ? [...state.review_receipts] : [],
    created_at: state.created_at,
    updated_at: state.updated_at,
  }
}

function validateState(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('LongWriter runtime state must be a JSON object')
  }
  if (raw.schema_version !== STATE_SCHEMA_VERSION) {
    throw new Error(`unsupported LongWriter runtime state schema: ${raw.schema_version}`)
  }
  if (!Number.isSafeInteger(raw.revision) || raw.revision < 0) {
    throw new Error('LongWriter runtime revision must be a non-negative safe integer')
  }
  if (!/^[a-f0-9]{64}$/.test(raw.snapshot_sha256 ?? '')) {
    throw new Error('LongWriter runtime snapshot_sha256 is invalid')
  }
  if (typeof raw.finalized !== 'boolean') {
    throw new Error('LongWriter runtime finalized must be boolean')
  }
  if (!Array.isArray(raw.review_receipts)) raw.review_receipts = []
  return raw
}

async function exists(filePath) {
  try {
    await stat(filePath)
    return true
  } catch (error) {
    if (error?.code === 'ENOENT') return false
    throw error
  }
}

async function atomicWrite(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true })
  const temporary = path.join(
    path.dirname(filePath),
    `.${path.basename(filePath)}.${process.pid}.${randomUUID()}.tmp`,
  )
  const handle = await open(temporary, 'wx', 0o600)
  try {
    await handle.writeFile(content, 'utf8')
    await handle.sync()
  } finally {
    await handle.close()
  }
  try {
    await rename(temporary, filePath)
  } catch (error) {
    await unlink(temporary).catch(() => {})
    throw error
  }
}

async function sleep(milliseconds) {
  await new Promise(resolve => setTimeout(resolve, milliseconds))
}

/**
 * Acquire a filesystem lock shared by CLI, MCP servers, harness adapters and
 * direct library users. mkdir is atomic across processes on local filesystems.
 */
export async function acquireWorkspaceLock(workspace, options = {}) {
  const root = resolveWorkspace(workspace)
  const lockTimeoutMs = options.timeoutMs ?? DEFAULT_LOCK_TIMEOUT_MS
  const staleLockMs = options.staleMs ?? DEFAULT_STALE_LOCK_MS
  if (!Number.isFinite(lockTimeoutMs) || lockTimeoutMs <= 0) {
    throw new TypeError('lock timeoutMs must be a positive number')
  }
  if (!Number.isFinite(staleLockMs) || staleLockMs <= LOCK_HEARTBEAT_MS * 2) {
    throw new TypeError(`lock staleMs must exceed ${LOCK_HEARTBEAT_MS * 2} ms`)
  }

  const runtimeDirectory = runtimePath(root)
  const lockDirectory = runtimePath(root, 'lock')
  const ownerPath = path.join(lockDirectory, 'owner.json')
  await mkdir(runtimeDirectory, { recursive: true, mode: 0o700 })
  const startedAt = Date.now()
  const localHostname = hostname()

  async function readOwner() {
    try {
      return JSON.parse(await readFile(ownerPath, 'utf8'))
    } catch (error) {
      if (error?.code === 'ENOENT' || error instanceof SyntaxError) return null
      throw error
    }
  }

  function ownerProcessAlive(owner) {
    if (
      !owner
      || owner.hostname !== localHostname
      || !Number.isSafeInteger(owner.pid)
      || owner.pid <= 0
    ) return null
    try {
      process.kill(owner.pid, 0)
      return true
    } catch (error) {
      if (error?.code === 'ESRCH') return false
      if (error?.code === 'EPERM') return true
      return null
    }
  }

  async function staleObservation() {
    const owner = await readOwner()
    let details
    try {
      details = await stat(ownerPath)
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error
      try {
        details = await stat(lockDirectory)
      } catch (directoryError) {
        if (directoryError?.code === 'ENOENT') return null
        throw directoryError
      }
    }
    return {
      token: owner?.token ?? null,
      stale: ownerProcessAlive(owner) === false || Date.now() - details.mtimeMs > staleLockMs,
    }
  }

  while (true) {
    const token = randomUUID()
    try {
      await mkdir(lockDirectory)
      const owner = {
        pid: process.pid,
        hostname: localHostname,
        token,
        acquired_at: new Date().toISOString(),
        heartbeat_at: new Date().toISOString(),
      }
      try {
        await writeFile(ownerPath, `${JSON.stringify(owner, null, 2)}\n`, {
          encoding: 'utf8',
          mode: 0o600,
        })
      } catch (error) {
        await rm(lockDirectory, { recursive: true, force: true })
        throw error
      }

      let released = false
      const heartbeat = setInterval(async () => {
        try {
          const current = await readOwner()
          if (current?.token !== token) {
            clearInterval(heartbeat)
            return
          }
          await writeFile(ownerPath, `${JSON.stringify({
            ...current,
            heartbeat_at: new Date().toISOString(),
          }, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 })
        } catch {
          clearInterval(heartbeat)
        }
      }, LOCK_HEARTBEAT_MS)
      heartbeat.unref?.()

      return async () => {
        if (released) return
        released = true
        clearInterval(heartbeat)
        const current = await readOwner().catch(() => null)
        if (current?.token === token) {
          await rm(lockDirectory, { recursive: true, force: true })
        }
      }
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error
      const observed = await staleObservation()
      if (observed?.stale) {
        const current = await staleObservation()
        if (current?.stale && current.token === observed.token) {
          await rm(lockDirectory, { recursive: true, force: true })
          continue
        }
      }
      if (Date.now() - startedAt >= lockTimeoutMs) {
        throw new Error(`timed out waiting for LongWriter workspace lock: ${root}`)
      }
      await sleep(25 + Math.floor(Math.random() * 50))
    }
  }
}

/**
 * Hash the human-readable canonical publication state. Runtime metadata is not
 * included, so out-of-band edits to project/article/manifest are detectable.
 */
export async function canonicalSnapshotSha256(workspace) {
  const root = resolveWorkspace(workspace)
  const files = ['project.json', 'article.md', 'assets/manifest.json']
  const hash = createHash('sha256')
  for (const relative of files) {
    const bytes = await readFile(path.join(root, relative))
    hash.update(relative, 'utf8')
    hash.update('\0', 'utf8')
    hash.update(String(bytes.byteLength), 'utf8')
    hash.update('\0', 'utf8')
    hash.update(bytes)
    hash.update('\0', 'utf8')
  }
  return hash.digest('hex')
}

async function readStateFile(workspace) {
  const filePath = runtimePath(workspace, RUNTIME_STATE_FILENAME)
  const raw = JSON.parse(await readFile(filePath, 'utf8'))
  return validateState(raw)
}

async function writeStateFile(workspace, state) {
  await atomicWrite(
    runtimePath(workspace, RUNTIME_STATE_FILENAME),
    `${JSON.stringify(validateState(state), null, 2)}\n`,
  )
}

async function appendOperation(workspace, operation) {
  await mkdir(runtimePath(workspace), { recursive: true, mode: 0o700 })
  await appendFile(
    runtimePath(workspace, OPERATIONS_FILENAME),
    `${JSON.stringify(operation)}\n`,
    { encoding: 'utf8', mode: 0o600 },
  )
}

function initialState(snapshot, revision = 0) {
  const now = new Date().toISOString()
  return {
    schema_version: STATE_SCHEMA_VERSION,
    revision,
    snapshot_sha256: snapshot,
    finalized: false,
    finalized_at: null,
    review_receipts: [],
    created_at: now,
    updated_at: now,
  }
}

async function adoptLegacyWorkspaceLocked(workspace) {
  const snapshot = await canonicalSnapshotSha256(workspace)
  const state = initialState(snapshot, 0)
  await writeStateFile(workspace, state)
  await appendOperation(workspace, {
    id: randomUUID(),
    operation: 'adopt_legacy_workspace',
    revision_before: null,
    revision_after: 0,
    snapshot_after: snapshot,
    committed_at: state.updated_at,
  })
  return state
}

async function loadOrAdoptStateLocked(workspace) {
  try {
    return await readStateFile(workspace)
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error
    return adoptLegacyWorkspaceLocked(workspace)
  }
}

async function assertSynchronized(workspace, state) {
  const actual = await canonicalSnapshotSha256(workspace)
  if (actual !== state.snapshot_sha256) {
    throw new Error(
      'canonical publication files changed outside LongWriter; '
      + `runtime snapshot=${state.snapshot_sha256}, actual=${actual}. `
      + 'Restore the files or deliberately adopt them in a new workspace.',
    )
  }
  return actual
}

function assertExpectedRevision(expectedRevision, actualRevision) {
  if (expectedRevision === undefined || expectedRevision === null) return
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0) {
    throw new TypeError('expected_revision must be a non-negative safe integer')
  }
  if (expectedRevision !== actualRevision) {
    const error = new Error(
      `revision conflict: expected ${expectedRevision}, current ${actualRevision}`,
    )
    error.code = 'LONGWRITER_REVISION_CONFLICT'
    error.expectedRevision = expectedRevision
    error.currentRevision = actualRevision
    throw error
  }
}

function sanitizeRuntimePatch(patch) {
  if (patch === undefined) return {}
  if (!patch || typeof patch !== 'object' || Array.isArray(patch)) {
    throw new TypeError('runtimePatch must be an object')
  }
  const allowed = new Set(['finalized', 'finalized_at', 'review_receipts'])
  for (const key of Object.keys(patch)) {
    if (!allowed.has(key)) throw new Error(`runtimePatch may not set ${key}`)
  }
  return patch
}

/**
 * Reset hidden runtime state after controlled publication initialization.
 * The caller must already hold the workspace lock.
 */
export async function initializeRuntimeStateLocked(workspace, options = {}) {
  const snapshot = await canonicalSnapshotSha256(workspace)
  const revision = options.revision ?? 1
  const state = initialState(snapshot, revision)
  await rm(runtimePath(workspace, REVIEWS_DIRECTORY), { recursive: true, force: true })
  await rm(runtimePath(workspace, OPERATIONS_FILENAME), { force: true })
  await writeStateFile(workspace, state)
  await appendOperation(workspace, {
    id: randomUUID(),
    operation: options.operation ?? 'initialize_publication',
    revision_before: null,
    revision_after: revision,
    snapshot_after: snapshot,
    committed_at: state.updated_at,
  })
  return publicRuntimeState(state)
}

export async function readRuntimeState(workspace, options = {}) {
  const root = resolveWorkspace(workspace)
  const release = await acquireWorkspaceLock(root, options.lock)
  try {
    const state = await loadOrAdoptStateLocked(root)
    await assertSynchronized(root, state)
    return publicRuntimeState(state)
  } finally {
    await release()
  }
}

/**
 * Execute one controlled mutation. A successful mutation advances the shared
 * revision exactly once; a rejected/no-op command leaves revision unchanged.
 */
export async function withPublicationTransaction(workspace, options, mutate) {
  const root = resolveWorkspace(workspace)
  if (typeof mutate !== 'function') throw new TypeError('mutate must be a function')
  const operation = options?.operation
  if (typeof operation !== 'string' || operation.trim().length === 0) {
    throw new TypeError('transaction operation must be a non-empty string')
  }
  const release = await acquireWorkspaceLock(root, options?.lock)
  try {
    const state = await loadOrAdoptStateLocked(root)
    await assertSynchronized(root, state)
    assertExpectedRevision(options?.expectedRevision, state.revision)
    if (state.finalized && options?.allowFinalized !== true) {
      throw new Error('publication is finalized; create a new workspace for further changes')
    }

    const outcome = await mutate({
      state: publicRuntimeState(state),
      workspace: root,
    })
    const normalized = (
      outcome
      && typeof outcome === 'object'
      && !Array.isArray(outcome)
      && ('result' in outcome || 'runtimePatch' in outcome || 'commit' in outcome)
    )
      ? outcome
      : { result: outcome }

    if (normalized.commit === false) {
      return {
        result: normalized.result,
        runtime: publicRuntimeState(state),
        committed: false,
      }
    }

    const runtimePatch = sanitizeRuntimePatch(normalized.runtimePatch)
    const snapshot = await canonicalSnapshotSha256(root)
    const now = new Date().toISOString()
    const nextState = validateState({
      ...state,
      ...runtimePatch,
      schema_version: STATE_SCHEMA_VERSION,
      revision: state.revision + 1,
      snapshot_sha256: snapshot,
      updated_at: now,
    })
    await writeStateFile(root, nextState)
    await appendOperation(root, {
      id: randomUUID(),
      operation: operation.trim(),
      revision_before: state.revision,
      revision_after: nextState.revision,
      snapshot_before: state.snapshot_sha256,
      snapshot_after: snapshot,
      metadata: options?.metadata ?? null,
      committed_at: now,
    })
    return {
      result: normalized.result,
      runtime: publicRuntimeState(nextState),
      committed: true,
    }
  } finally {
    await release()
  }
}

export async function writeReviewReceipt(workspace, receipt) {
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
    throw new TypeError('review receipt must be an object')
  }
  if (typeof receipt.id !== 'string' || !/^[A-Za-z0-9_-]+$/.test(receipt.id)) {
    throw new TypeError('review receipt id is invalid')
  }
  const relativePath = `${RUNTIME_DIRECTORY}/${REVIEWS_DIRECTORY}/${receipt.id}.json`
  const absolutePath = path.join(resolveWorkspace(workspace), relativePath)
  if (await exists(absolutePath)) throw new Error(`review receipt already exists: ${receipt.id}`)
  const content = `${JSON.stringify(receipt, null, 2)}\n`
  await atomicWrite(absolutePath, content)
  return {
    path: relativePath,
    sha256: createHash('sha256').update(content, 'utf8').digest('hex'),
  }
}

export async function readReviewReceipt(workspace, relativePath, expectedSha256) {
  if (typeof relativePath !== 'string') throw new TypeError('review receipt path must be a string')
  const normalized = relativePath.replaceAll('\\', '/')
  const prefix = `${RUNTIME_DIRECTORY}/${REVIEWS_DIRECTORY}/`
  if (!normalized.startsWith(prefix) || normalized.includes('..') || !normalized.endsWith('.json')) {
    throw new Error('review receipt path is outside the LongWriter runtime directory')
  }
  if (expectedSha256 !== undefined && !/^[a-f0-9]{64}$/.test(expectedSha256)) {
    throw new TypeError('expected review receipt SHA-256 is invalid')
  }
  const content = await readFile(path.join(resolveWorkspace(workspace), normalized), 'utf8')
  const actualSha256 = createHash('sha256').update(content, 'utf8').digest('hex')
  if (expectedSha256 !== undefined && actualSha256 !== expectedSha256) {
    throw new Error(`review receipt hash mismatch: ${normalized}`)
  }
  return JSON.parse(content)
}
