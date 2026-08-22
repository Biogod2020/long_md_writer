import { createHash, randomUUID } from 'node:crypto'
import { link, lstat, mkdir, open, readFile, rename, stat, unlink } from 'node:fs/promises'
import path from 'node:path'

export const PROJECT_FILENAME = 'project.json'
export const ARTICLE_FILENAME = 'article.md'
export const ASSET_MANIFEST_FILENAME = 'assets/manifest.json'

const SAFE_ID = /^[A-Za-z0-9_-]+$/
const SHA256 = /^[a-f0-9]{64}$/
const CONTROL_MARKER = '<!-- longwriter:'
const workspaceQueues = new Map()

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function requireText(value, name) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${name} must be a non-empty string`)
  }
  return value.trim()
}

function requireSafeId(value, name) {
  const normalized = requireText(value, name)
  if (normalized.length > 100 || !SAFE_ID.test(normalized)) {
    throw new TypeError(`${name} may contain only letters, digits, '-' and '_'`)
  }
  return normalized
}

function requireSha256(value, name) {
  const normalized = requireText(value, name).toLowerCase()
  if (!SHA256.test(normalized)) throw new TypeError(`${name} must be a lowercase SHA-256 hex digest`)
  return normalized
}

function requireStringArray(value, name, { maximum = 100, allowEmpty = true } = {}) {
  if (!Array.isArray(value)) throw new TypeError(`${name} must be an array`)
  if (value.length > maximum) throw new TypeError(`${name} may contain at most ${maximum} values`)
  const normalized = value.map((item, index) => requireText(item, `${name}[${index}]`))
  if (!allowEmpty && normalized.length === 0) throw new TypeError(`${name} must not be empty`)
  return normalized
}

function requirePositiveInteger(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isSafeInteger(resolved) || resolved < 1) {
    throw new TypeError(`${name} must be a positive safe integer`)
  }
  return resolved
}

function requireRatio(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (typeof resolved !== 'number' || !Number.isFinite(resolved) || resolved <= 0 || resolved > 1.5) {
    throw new TypeError(`${name} must be a finite number in (0, 1.5]`)
  }
  return resolved
}

export function normalizeProject(input) {
  if (!isPlainObject(input)) throw new TypeError('project must be a JSON object')
  if (input.mode !== undefined && input.mode !== 'markdown') {
    throw new TypeError('the DSH-native preview currently supports mode=markdown only')
  }
  if (!Array.isArray(input.sections) || input.sections.length === 0 || input.sections.length > 100) {
    throw new TypeError('project.sections must contain between 1 and 100 sections')
  }

  const sections = input.sections.map((raw, index) => {
    if (!isPlainObject(raw)) throw new TypeError(`project.sections[${index}] must be an object`)
    return {
      id: requireSafeId(raw.id, `project.sections[${index}].id`),
      title: requireText(raw.title, `project.sections[${index}].title`),
      objective: requireText(raw.objective, `project.sections[${index}].objective`),
      target_words: Math.min(50_000, requirePositiveInteger(raw.target_words, `project.sections[${index}].target_words`, 800)),
      required_evidence: Array.isArray(raw.required_evidence)
        ? raw.required_evidence.map((item, evidenceIndex) => requireText(
          item,
          `project.sections[${index}].required_evidence[${evidenceIndex}]`,
        ))
        : [],
    }
  })

  const ids = sections.map(section => section.id)
  if (new Set(ids).size !== ids.length) throw new TypeError('section ids must be unique')

  const visualContractInput = input.visual_contract === undefined ? {} : input.visual_contract
  if (!isPlainObject(visualContractInput)) {
    throw new TypeError('project.visual_contract must be an object')
  }
  if (visualContractInput.schema_version !== undefined && visualContractInput.schema_version !== 1) {
    throw new TypeError('project.visual_contract.schema_version must be 1')
  }
  const figuresInput = visualContractInput.figures === undefined ? [] : visualContractInput.figures
  if (!Array.isArray(figuresInput) || figuresInput.length > 100) {
    throw new TypeError('project.visual_contract.figures must contain at most 100 figures')
  }
  const visualFigures = figuresInput.map((raw, index) => {
    if (!isPlainObject(raw)) throw new TypeError(`project.visual_contract.figures[${index}] must be an object`)
    const sectionId = requireSafeId(raw.section_id, `project.visual_contract.figures[${index}].section_id`)
    if (!ids.includes(sectionId)) {
      throw new TypeError(`project.visual_contract.figures[${index}].section_id is not a planned section`)
    }
    const requiredLabels = raw.required_labels === undefined ? [] : requireStringArray(
      raw.required_labels,
      `project.visual_contract.figures[${index}].required_labels`,
      { maximum: 40 },
    )
    if (new Set(requiredLabels).size !== requiredLabels.length) {
      throw new TypeError(`project.visual_contract.figures[${index}].required_labels must be unique`)
    }
    if (raw.review_required !== undefined && typeof raw.review_required !== 'boolean') {
      throw new TypeError(`project.visual_contract.figures[${index}].review_required must be boolean`)
    }
    return {
      id: requireSafeId(raw.id, `project.visual_contract.figures[${index}].id`),
      section_id: sectionId,
      kind: requireText(raw.kind, `project.visual_contract.figures[${index}].kind`),
      purpose: requireText(raw.purpose, `project.visual_contract.figures[${index}].purpose`),
      required_labels: requiredLabels,
      review_required: raw.review_required !== false,
    }
  })
  const visualIds = visualFigures.map(figure => figure.id)
  if (new Set(visualIds).size !== visualIds.length) {
    throw new TypeError('project.visual_contract.figure ids must be unique')
  }

  const quality = isPlainObject(input.quality_contract) ? input.quality_contract : {}
  return {
    schema_version: 1,
    title: requireText(input.title, 'project.title'),
    objective: requireText(input.objective, 'project.objective'),
    audience: requireText(input.audience ?? 'general technical readers', 'project.audience'),
    language: requireText(input.language ?? 'zh-CN', 'project.language'),
    mode: 'markdown',
    sections,
    visual_contract: {
      schema_version: 1,
      figures: visualFigures,
    },
    quality_contract: {
      minimum_section_ratio: requireRatio(
        quality.minimum_section_ratio,
        'project.quality_contract.minimum_section_ratio',
        0.75,
      ),
      minimum_total_ratio: requireRatio(
        quality.minimum_total_ratio,
        'project.quality_contract.minimum_total_ratio',
        0.75,
      ),
      minimum_review_score: Math.min(100, requirePositiveInteger(
        quality.minimum_review_score,
        'project.quality_contract.minimum_review_score',
        85,
      )),
      require_zero_placeholders: quality.require_zero_placeholders !== false,
      require_review: quality.require_review !== false,
    },
  }
}

export function sectionStartMarker(sectionId) {
  return `<!-- longwriter:section ${sectionId}:start -->`
}

export function sectionEndMarker(sectionId) {
  return `<!-- longwriter:section ${sectionId}:end -->`
}

export function chunkStartMarker(chunkId, sectionId) {
  return `<!-- longwriter:chunk ${chunkId} section=${sectionId}:start -->`
}

export function chunkEndMarker(chunkId) {
  return `<!-- longwriter:chunk ${chunkId}:end -->`
}

function scaffoldArticle(project) {
  const sections = project.sections.map(section => [
    sectionStartMarker(section.id),
    `## ${section.title}`,
    '',
    sectionEndMarker(section.id),
  ].join('\n'))
  return `# ${project.title}\n\n${sections.join('\n\n')}\n`
}

function emptyAssetManifest() {
  return {
    schema_version: 2,
    assets: [],
    visual_preflights: [],
    visual_reviews: [],
  }
}

function resolveWorkspace(workspace) {
  if (typeof workspace !== 'string' || workspace.trim().length === 0) {
    throw new TypeError('workspace must be a non-empty path')
  }
  return path.resolve(workspace)
}

async function exists(filePath) {
  try {
    await stat(filePath)
    return true
  } catch (error) {
    if (error && error.code === 'ENOENT') return false
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

function withWorkspaceLock(workspace, operation) {
  const key = resolveWorkspace(workspace)
  const previous = workspaceQueues.get(key) ?? Promise.resolve()
  const run = previous.then(operation)
  let tracked
  tracked = run.then(
    () => undefined,
    () => undefined,
  ).finally(() => {
    if (workspaceQueues.get(key) === tracked) workspaceQueues.delete(key)
  })
  workspaceQueues.set(key, tracked)
  return run
}

export async function initializeProject(workspace, input, options = {}) {
  const root = resolveWorkspace(workspace)
  const project = normalizeProject(input)
  return withWorkspaceLock(root, async () => {
    await mkdir(root, { recursive: true })
    const projectPath = path.join(root, PROJECT_FILENAME)
    const articlePath = path.join(root, ARTICLE_FILENAME)
    const manifestPath = path.join(root, ASSET_MANIFEST_FILENAME)
    const occupied = await Promise.all([projectPath, articlePath, manifestPath].map(exists))
    if (occupied.some(Boolean) && options.overwrite !== true) {
      if (occupied.every(Boolean)) {
        const existing = await readProject(root)
        if (JSON.stringify(existing) === JSON.stringify(project)) {
          return { created: false, project: existing, status: await publicationStatus(root) }
        }
      }
      throw new Error('publication workspace already contains canonical files; use a new workspace')
    }
    await atomicWrite(projectPath, `${JSON.stringify(project, null, 2)}\n`)
    await atomicWrite(articlePath, scaffoldArticle(project))
    await atomicWrite(manifestPath, `${JSON.stringify(emptyAssetManifest(), null, 2)}\n`)
    return { created: true, project, status: await publicationStatus(root) }
  })
}

export async function readProject(workspace) {
  const root = resolveWorkspace(workspace)
  const raw = JSON.parse(await readFile(path.join(root, PROJECT_FILENAME), 'utf8'))
  return normalizeProject(raw)
}

/**
 * Resolve a visual-plan record from the canonical project contract.
 * The returned record is normalized, so callers cannot bypass section or id
 * validation by supplying an ad-hoc object to a later asset operation.
 */
export async function resolveVisualPlan(workspace, visualPlanId) {
  const id = requireSafeId(visualPlanId, 'visual_plan_id')
  const project = await readProject(workspace)
  const figure = project.visual_contract.figures.find(item => item.id === id)
  if (!figure) throw new Error(`unknown visual_plan_id: ${id}`)
  return figure
}

/**
 * Replace only project.json.visual_contract through the domain store. The
 * project schema remains the canonical plan record; no fourth workspace file
 * is introduced for visuals.
 */
export async function setVisualContract(workspace, visualContract) {
  const root = resolveWorkspace(workspace)
  return withWorkspaceLock(root, async () => {
    const project = await readProject(root)
    const normalized = normalizeProject({ ...project, visual_contract: visualContract })
    const manifest = await readAssetManifest(root)
    for (const entry of manifest.assets) {
      if (!entry?.visual_plan_id) continue
      const before = project.visual_contract.figures.find(figure => figure.id === entry.visual_plan_id)
      const after = normalized.visual_contract.figures.find(figure => figure.id === entry.visual_plan_id)
      if (!before || !after || JSON.stringify(before) !== JSON.stringify(after)) {
        throw new Error(`visual plan ${entry.visual_plan_id} is immutable after an SVG asset is registered`)
      }
    }
    await atomicWrite(path.join(root, PROJECT_FILENAME), `${JSON.stringify(normalized, null, 2)}\n`)
    return normalized.visual_contract
  })
}

export async function readArticle(workspace) {
  const root = resolveWorkspace(workspace)
  return readFile(path.join(root, ARTICLE_FILENAME), 'utf8')
}

export async function readAssetManifest(workspace) {
  const root = resolveWorkspace(workspace)
  const raw = JSON.parse(await readFile(path.join(root, ASSET_MANIFEST_FILENAME), 'utf8'))
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.assets)) {
    throw new Error('asset manifest must be an object with an assets array')
  }
  // Version 2 predates visual receipts. Treat absent receipt arrays as empty
  // on read, then add them only on the next controlled manifest mutation.
  if (!Array.isArray(raw.visual_preflights)) raw.visual_preflights = []
  if (!Array.isArray(raw.visual_reviews)) raw.visual_reviews = []
  return raw
}

async function atomicWriteBytes(filePath, bytes) {
  await mkdir(path.dirname(filePath), { recursive: true })
  const temporary = path.join(
    path.dirname(filePath),
    `.${path.basename(filePath)}.${process.pid}.${randomUUID()}.tmp`,
  )
  const handle = await open(temporary, 'wx', 0o600)
  try {
    await handle.writeFile(bytes)
    await handle.sync()
  } finally {
    await handle.close()
  }
  try {
    // link() creates the final name only when it does not already exist.
    // Unlike rename(), it cannot replace a pre-existing protected asset.
    await link(temporary, filePath)
    await unlink(temporary)
  } catch (error) {
    await unlink(temporary).catch(() => {})
    throw error
  }
}

const ASSET_REQUIRED_TEXT_FIELDS = ['source', 'caption', 'alt_text', 'provenance', 'licence']

function normalizeDerivative(value) {
  if (value === undefined) return undefined
  if (!isPlainObject(value)) throw new TypeError('asset derivative_of must be an object')
  const purpose = requireText(value.purpose, 'asset derivative_of.purpose')
  if (purpose.length > 120) throw new TypeError('asset derivative_of.purpose is too long')
  return {
    asset_id: requireSafeId(value.asset_id, 'asset derivative_of.asset_id'),
    asset_sha256: requireSha256(value.asset_sha256, 'asset derivative_of.asset_sha256'),
    purpose,
  }
}

function assetPath(root, relative) {
  if (typeof relative !== 'string' || !relative.startsWith('assets/')) {
    throw new Error('asset path must live under assets/')
  }
  if (relative.split('/').includes('..') || relative.includes('\\')) {
    throw new Error('asset path must not traverse or escape assets/')
  }
  const target = path.resolve(root, relative)
  const assetsRoot = path.resolve(root, 'assets')
  if (!target.startsWith(assetsRoot + path.sep)) {
    throw new Error('asset path escapes assets/')
  }
  return target
}

function findAssetById(manifest, id) {
  return manifest.assets.find(entry => entry && entry.id === id) ?? null
}

async function currentAsset(root, manifest, assetId, expectedSha, name = 'asset') {
  const id = requireSafeId(assetId, `${name}_id`)
  const sha256 = requireSha256(expectedSha, `${name}_sha256`)
  const entry = findAssetById(manifest, id)
  if (!entry) throw new Error(`${name} is not registered: ${id}`)
  if (entry.sha256 !== sha256) throw new Error(`${name} hash does not match the manifest: ${id}`)
  const target = assetPath(root, entry.path)
  const details = await lstat(target)
  if (!details.isFile() || details.isSymbolicLink()) throw new Error(`${name} must be a regular local file: ${id}`)
  const bytes = await readFile(target)
  const actual = createHash('sha256').update(bytes).digest('hex')
  if (actual !== sha256) throw new Error(`${name} hash does not match the physical file: ${id}`)
  return { entry, bytes, sha256, path: entry.path }
}

/**
 * Register one physical asset under assets/ and append its provenance entry
 * to assets/manifest.json. Canonical asset mutations flow through this domain
 * store only: safe id, path containment, hash binding, duplicate rejection,
 * per-workspace serialization, atomic asset creation, and manifest replacement.
 *
 * @param {string} workspace  publication workspace root
 * @param {object} input      { id, source, path, caption, alt_text,
 *                             provenance, licence, used_in, bytes }
 */
export async function registerAsset(workspace, input) {
  const root = resolveWorkspace(workspace)
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('asset registration requires an object')
  }
  const id = requireSafeId(input.id, 'asset id')
  const rel = input.path
  const target = assetPath(root, rel)
  for (const field of ASSET_REQUIRED_TEXT_FIELDS) {
    if (typeof input[field] !== 'string' || input[field].trim().length === 0) {
      throw new TypeError(`asset ${field} must be a non-empty string`)
    }
  }
  if (!Array.isArray(input.used_in)) throw new TypeError('asset used_in must be an array')
  const usedIn = requireStringArray(input.used_in, 'asset used_in', { maximum: 100 })
  const visualPlanId = input.visual_plan_id === undefined
    ? undefined
    : requireSafeId(input.visual_plan_id, 'asset visual_plan_id')
  const supersedesAssetId = input.supersedes_asset_id === undefined
    ? undefined
    : requireSafeId(input.supersedes_asset_id, 'asset supersedes_asset_id')
  const derivativeOf = normalizeDerivative(input.derivative_of)
  const bytes = input.bytes
  if (!(bytes instanceof Uint8Array) && !Buffer.isBuffer(bytes)) {
    throw new TypeError('asset bytes must be provided as a Uint8Array or Buffer')
  }
  if (bytes.byteLength === 0) throw new Error('asset bytes must not be empty')
  return withWorkspaceLock(root, async () => {
    const manifest = await readAssetManifest(root)
    if (manifest.assets.some(entry => entry && entry.id === id)) {
      throw new Error(`duplicate asset id: ${id}`)
    }
    if (manifest.assets.some(entry => entry && entry.path === rel)) {
      throw new Error(`asset path already registered: ${rel}`)
    }
    if (await exists(target)) {
      throw new Error(`asset file already exists: ${rel}`)
    }
    if (visualPlanId !== undefined) {
      const plan = await resolveVisualPlan(root, visualPlanId)
      if (!rel.startsWith('assets/svg/') || !rel.endsWith('.svg')) {
        throw new Error('a visual_plan_id may be bound only to an assets/svg/*.svg asset')
      }
      const plannedAssets = manifest.assets.filter(entry => entry && entry.visual_plan_id === plan.id)
      if (plannedAssets.length > 0) {
        if (!supersedesAssetId) {
          throw new Error(`a new SVG revision for visual plan ${plan.id} requires supersedes_asset_id`)
        }
        const predecessor = plannedAssets.find(entry => entry.id === supersedesAssetId)
        if (!predecessor) {
          throw new Error('supersedes_asset_id must name an SVG asset bound to the same visual plan')
        }
        if (plannedAssets.some(entry => entry.supersedes_asset_id === predecessor.id)) {
          throw new Error(`supersedes_asset_id already has a successor: ${predecessor.id}`)
        }
      } else if (supersedesAssetId !== undefined) {
        throw new Error('the first SVG for a visual plan must not declare supersedes_asset_id')
      }
      if (!usedIn.includes(plan.section_id)) {
        throw new Error(`asset used_in must include the planned section: ${plan.section_id}`)
      }
    } else if (supersedesAssetId !== undefined) {
      throw new Error('supersedes_asset_id requires visual_plan_id')
    }
    const sha256 = createHash('sha256').update(bytes).digest('hex')
    let assetWritten = false
    try {
      await atomicWriteBytes(target, bytes)
      assetWritten = true
      const entry = {
        id,
        source: input.source,
        path: rel,
        caption: input.caption.trim(),
        alt_text: input.alt_text.trim(),
        provenance: input.provenance.trim(),
        licence: input.licence.trim(),
        used_in: usedIn,
        sha256,
      }
      if (visualPlanId !== undefined) entry.visual_plan_id = visualPlanId
      if (supersedesAssetId !== undefined) entry.supersedes_asset_id = supersedesAssetId
      if (derivativeOf !== undefined) entry.derivative_of = derivativeOf
      manifest.assets.push(entry)
      await atomicWrite(path.join(root, ASSET_MANIFEST_FILENAME), `${JSON.stringify(manifest, null, 2)}\n`)
      return { entry, sha256, path: rel }
    } catch (error) {
      if (assetWritten) await unlink(target).catch(() => {})
      throw error
    }
  })
}

/** Read one registered regular asset and re-verify its manifest hash. */
export async function readRegisteredAsset(workspace, assetId) {
  const root = resolveWorkspace(workspace)
  const id = requireSafeId(assetId, 'asset_id')
  const manifest = await readAssetManifest(root)
  const entry = findAssetById(manifest, id)
  if (!entry) throw new Error(`asset is not registered: ${id}`)
  return currentAsset(root, manifest, id, entry.sha256, 'asset')
}

function receiptText(value, name, { maximum = 2000 } = {}) {
  const text = requireText(value, name)
  if (text.length > maximum) throw new TypeError(`${name} is too long`)
  return text
}

function receiptTextArray(value, name, maximum = 100) {
  const items = value === undefined ? [] : requireStringArray(value, name, { maximum })
  return items.map((item, index) => receiptText(item, `${name}[${index}]`, { maximum: 500 }))
}

function visualPlanForProject(project, id) {
  const plan = project.visual_contract.figures.find(figure => figure.id === id)
  if (!plan) throw new Error(`unknown visual_plan_id: ${id}`)
  return plan
}

function preflightRecord(manifest, id) {
  return manifest.visual_preflights.find(item => item && item.id === id) ?? null
}

function isPng(bytes) {
  return bytes.byteLength >= 8
    && bytes[0] === 137
    && bytes[1] === 80
    && bytes[2] === 78
    && bytes[3] === 71
    && bytes[4] === 13
    && bytes[5] === 10
    && bytes[6] === 26
    && bytes[7] === 10
}

/**
 * Append immutable geometry-preflight evidence. Both the reviewed SVG and
 * retained PNG preview are re-hashed before the receipt is written.
 */
export async function appendVisualPreflight(workspace, input) {
  const root = resolveWorkspace(workspace)
  if (!isPlainObject(input)) throw new TypeError('visual preflight requires an object')
  return withWorkspaceLock(root, async () => {
    const manifest = await readAssetManifest(root)
    const project = await readProject(root)
    const assetId = requireSafeId(input.asset_id, 'asset_id')
    const assetSha = requireSha256(input.asset_sha256, 'asset_sha256')
    const planId = requireSafeId(input.visual_plan_id, 'visual_plan_id')
    const previewId = requireSafeId(input.preview_asset_id, 'preview_asset_id')
    const previewSha = requireSha256(input.preview_sha256, 'preview_sha256')
    const asset = await currentAsset(root, manifest, assetId, assetSha, 'preflight asset')
    const preview = await currentAsset(root, manifest, previewId, previewSha, 'preflight preview')
    const plan = visualPlanForProject(project, planId)
    if (asset.entry.visual_plan_id !== plan.id) {
      throw new Error('preflight visual_plan_id does not match the registered SVG asset')
    }
    const derivative = preview.entry.derivative_of
    if (!isPlainObject(derivative)
      || derivative.asset_id !== assetId
      || derivative.asset_sha256 !== assetSha
      || derivative.purpose !== 'svg-preview') {
      throw new Error('preflight preview must be a registered svg-preview derivative of the SVG asset')
    }
    if (!preview.entry.path.startsWith('assets/reviews/') || !preview.entry.path.endsWith('.png') || !isPng(preview.bytes)) {
      throw new Error('preflight preview must be a registered PNG under assets/reviews/')
    }
    if (typeof input.passed !== 'boolean') throw new TypeError('preflight passed must be boolean')
    const metricMode = receiptText(input.metric_mode, 'preflight metric_mode', { maximum: 80 })
    const renderer = receiptText(input.renderer, 'preflight renderer', { maximum: 80 })
    const receipt = {
      id: `preflight-${randomUUID()}`,
      asset_id: assetId,
      asset_sha256: assetSha,
      visual_plan_id: planId,
      preview_asset_id: previewId,
      preview_sha256: previewSha,
      metric_mode: metricMode,
      renderer,
      passed: input.passed,
      issues: receiptTextArray(input.issues, 'preflight issues'),
      warnings: receiptTextArray(input.warnings, 'preflight warnings'),
      created_at: new Date().toISOString(),
    }
    manifest.visual_preflights.push(receipt)
    await atomicWrite(path.join(root, ASSET_MANIFEST_FILENAME), `${JSON.stringify(manifest, null, 2)}\n`)
    return receipt
  })
}

/**
 * Append an explicit human or fresh-reviewer inspection receipt for a retained
 * PNG preview. It cannot be written for a different SVG, preview, or plan.
 */
export async function appendVisualReview(workspace, input) {
  const root = resolveWorkspace(workspace)
  if (!isPlainObject(input)) throw new TypeError('visual review requires an object')
  return withWorkspaceLock(root, async () => {
    const manifest = await readAssetManifest(root)
    const project = await readProject(root)
    const assetId = requireSafeId(input.asset_id, 'asset_id')
    const preflightId = requireSafeId(input.preflight_id, 'preflight_id')
    const preflight = preflightRecord(manifest, preflightId)
    if (!preflight) throw new Error(`unknown preflight_id: ${preflightId}`)
    if (preflight.asset_id !== assetId || preflight.passed !== true) {
      throw new Error('visual review requires a passing preflight for the same SVG asset')
    }
    const asset = await currentAsset(root, manifest, assetId, preflight.asset_sha256, 'review asset')
    const preview = await currentAsset(root, manifest, preflight.preview_asset_id, preflight.preview_sha256, 'review preview')
    const plan = visualPlanForProject(project, preflight.visual_plan_id)
    if (asset.entry.visual_plan_id !== plan.id) {
      throw new Error('review visual plan no longer matches the registered SVG asset')
    }
    const derivative = preview.entry.derivative_of
    if (!isPlainObject(derivative)
      || derivative.asset_id !== assetId
      || derivative.asset_sha256 !== preflight.asset_sha256
      || derivative.purpose !== 'svg-preview') {
      throw new Error('review preview no longer binds to the reviewed SVG asset')
    }
    if (!preview.entry.path.startsWith('assets/reviews/') || !preview.entry.path.endsWith('.png') || !isPng(preview.bytes)) {
      throw new Error('review preview must remain a registered PNG under assets/reviews/')
    }
    const verdict = receiptText(input.verdict, 'review verdict', { maximum: 10 })
    if (verdict !== 'pass' && verdict !== 'fail') throw new TypeError('review verdict must be pass or fail')
    const checkedLabels = receiptTextArray(input.checked_labels, 'review checked_labels', 40)
    if (new Set(checkedLabels).size !== checkedLabels.length) {
      throw new TypeError('review checked_labels must be unique')
    }
    if (verdict === 'pass' && !plan.required_labels.every(label => checkedLabels.includes(label))) {
      throw new Error('a passing review must confirm every required label')
    }
    const receipt = {
      id: `review-${randomUUID()}`,
      asset_id: assetId,
      asset_sha256: preflight.asset_sha256,
      visual_plan_id: plan.id,
      preflight_id: preflight.id,
      preview_asset_id: preflight.preview_asset_id,
      preview_sha256: preflight.preview_sha256,
      reviewer: receiptText(input.reviewer, 'review reviewer', { maximum: 200 }),
      verdict,
      summary: receiptText(input.summary, 'review summary', { maximum: 4000 }),
      findings: receiptTextArray(input.findings, 'review findings'),
      checked_labels: checkedLabels,
      reviewed_at: new Date().toISOString(),
    }
    manifest.visual_reviews.push(receipt)
    await atomicWrite(path.join(root, ASSET_MANIFEST_FILENAME), `${JSON.stringify(manifest, null, 2)}\n`)
    return receipt
  })
}

export function countWords(text) {
  if (typeof text !== 'string' || text.length === 0) return 0
  const cjk = text.match(/[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/g)?.length ?? 0
  const latin = text
    .replace(/[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/g, ' ')
    .match(/[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu)?.length ?? 0
  return cjk + latin
}

export function sha256Text(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex')
}

function assertChunkMarkdown(markdown) {
  const content = requireText(markdown, 'markdown')
  if (Buffer.byteLength(content, 'utf8') > 512_000) {
    throw new Error('one chunk may not exceed 512000 UTF-8 bytes')
  }
  if (content.includes(CONTROL_MARKER)) {
    throw new Error('chunk markdown may not contain longwriter control markers')
  }
  return content
}

function findSectionRegion(article, sectionId) {
  const startMarker = sectionStartMarker(sectionId)
  const endMarker = sectionEndMarker(sectionId)
  const start = article.indexOf(startMarker)
  const end = article.indexOf(endMarker)
  if (start < 0 || end < 0 || end <= start) {
    throw new Error(`article section markers are missing or corrupt for ${sectionId}`)
  }
  return {
    start,
    contentStart: start + startMarker.length,
    end,
    endAfter: end + endMarker.length,
    text: article.slice(start + startMarker.length, end),
  }
}

export function parseChunks(article) {
  const starts = [...article.matchAll(/<!-- longwriter:chunk ([A-Za-z0-9_-]+) section=([A-Za-z0-9_-]+):start -->/g)]
  const ends = [...article.matchAll(/<!-- longwriter:chunk ([A-Za-z0-9_-]+):end -->/g)]
  const chunks = []
  const pattern = /<!-- longwriter:chunk ([A-Za-z0-9_-]+) section=([A-Za-z0-9_-]+):start -->\n([\s\S]*?)\n<!-- longwriter:chunk \1:end -->/g
  for (const match of article.matchAll(pattern)) {
    chunks.push({
      id: match[1],
      section_id: match[2],
      markdown: match[3],
      start: match.index,
      end: match.index + match[0].length,
    })
  }
  if (starts.length !== ends.length || chunks.length !== starts.length) {
    throw new Error('article contains unbalanced or malformed chunk markers')
  }
  const ids = chunks.map(chunk => chunk.id)
  if (new Set(ids).size !== ids.length) throw new Error('article contains duplicate chunk ids')
  return chunks
}

export async function commitChunk(workspace, input) {
  const root = resolveWorkspace(workspace)
  const sectionId = requireSafeId(input?.section_id, 'section_id')
  const chunkId = requireSafeId(input?.chunk_id, 'chunk_id')
  const markdown = assertChunkMarkdown(input?.markdown)
  return withWorkspaceLock(root, async () => {
    const project = await readProject(root)
    if (!project.sections.some(section => section.id === sectionId)) {
      throw new Error(`unknown section_id: ${sectionId}`)
    }
    const article = await readArticle(root)
    if (parseChunks(article).some(chunk => chunk.id === chunkId)) {
      throw new Error(`chunk_id already exists: ${chunkId}`)
    }
    const region = findSectionRegion(article, sectionId)
    const block = `${chunkStartMarker(chunkId, sectionId)}\n${markdown}\n${chunkEndMarker(chunkId)}`
    const before = article.slice(0, region.end).replace(/[ \t]*$/u, '')
    const after = article.slice(region.end)
    const updated = `${before}\n\n${block}\n\n${after}`
    await atomicWrite(path.join(root, ARTICLE_FILENAME), updated)
    return publicationStatus(root)
  })
}

export async function reviseChunk(workspace, input) {
  const root = resolveWorkspace(workspace)
  const chunkId = requireSafeId(input?.chunk_id, 'chunk_id')
  const markdown = assertChunkMarkdown(input?.markdown)
  return withWorkspaceLock(root, async () => {
    const article = await readArticle(root)
    const chunks = parseChunks(article)
    const chunk = chunks.find(item => item.id === chunkId)
    if (!chunk) throw new Error(`unknown chunk_id: ${chunkId}`)
    const replacement = `${chunkStartMarker(chunk.id, chunk.section_id)}\n${markdown}\n${chunkEndMarker(chunk.id)}`
    const updated = article.slice(0, chunk.start) + replacement + article.slice(chunk.end)
    await atomicWrite(path.join(root, ARTICLE_FILENAME), updated)
    return publicationStatus(root)
  })
}

function sectionText(article, sectionId) {
  const region = findSectionRegion(article, sectionId)
  return region.text
    .replace(/<!-- longwriter:[^>]+-->/g, ' ')
    .replace(/^##\s+.*$/gm, ' ')
}

export async function publicationStatus(workspace) {
  const root = resolveWorkspace(workspace)
  const [project, article] = await Promise.all([readProject(root), readArticle(root)])
  const chunks = parseChunks(article)
  const sections = project.sections.map(section => {
    const wordCount = countWords(sectionText(article, section.id))
    const sectionChunks = chunks.filter(chunk => chunk.section_id === section.id).map(chunk => chunk.id)
    return {
      id: section.id,
      title: section.title,
      target_words: section.target_words,
      word_count: wordCount,
      completion_ratio: Number((wordCount / section.target_words).toFixed(3)),
      chunk_ids: sectionChunks,
    }
  })
  const totalWords = sections.reduce((sum, section) => sum + section.word_count, 0)
  const targetWords = sections.reduce((sum, section) => sum + section.target_words, 0)
  return {
    project_title: project.title,
    objective: project.objective,
    article_sha256: sha256Text(article),
    total_words: totalWords,
    target_words: targetWords,
    completion_ratio: Number((totalWords / targetWords).toFixed(3)),
    chunks: chunks.length,
    sections,
  }
}
