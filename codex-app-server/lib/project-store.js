import { createHash, randomUUID } from 'node:crypto'
import { link, lstat, mkdir, open, readFile, rename, stat, unlink } from 'node:fs/promises'
import path from 'node:path'

import { DESIGN_CHECK_KEYS, normalizeDesignBrief } from '../svg/design.js'

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

function requireNonNegativeInteger(value, name, fallback = 0) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isSafeInteger(resolved) || resolved < 0) {
    throw new TypeError(`${name} must be a non-negative safe integer`)
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


function requireUpperRatio(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (typeof resolved !== 'number' || !Number.isFinite(resolved) || resolved < 1 || resolved > 4) {
    throw new TypeError(`${name} must be a finite number in [1, 4]`)
  }
  return resolved
}

function requireUnitRatio(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (typeof resolved !== 'number' || !Number.isFinite(resolved) || resolved < 0 || resolved > 1) {
    throw new TypeError(`${name} must be a finite number in [0, 1]`)
  }
  return resolved
}

export function normalizeProject(input) {
  if (!isPlainObject(input)) throw new TypeError('project must be a JSON object')
  if (input.mode !== undefined && input.mode !== 'markdown') {
    throw new TypeError('LongMDWriter currently supports mode=markdown only')
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
  const visualSchemaVersion = visualContractInput.schema_version ?? 1
  if (visualSchemaVersion !== 1 && visualSchemaVersion !== 2) {
    throw new TypeError('project.visual_contract.schema_version must be 1 or 2')
  }
  const figuresInput = visualContractInput.figures === undefined ? [] : visualContractInput.figures
  if (!Array.isArray(figuresInput) || figuresInput.length > 100) {
    throw new TypeError('project.visual_contract.figures must contain at most 100 figures')
  }
  const figureStart = requirePositiveInteger(
    visualContractInput.figure_start,
    'project.visual_contract.figure_start',
    1,
  )
  const minimumFigures = requireNonNegativeInteger(
    visualContractInput.minimum_figures,
    'project.visual_contract.minimum_figures',
  )
  const requiredSections = visualContractInput.required_sections === undefined
    ? []
    : requireStringArray(
      visualContractInput.required_sections,
      'project.visual_contract.required_sections',
      { maximum: 100 },
    ).map((sectionId, index) => requireSafeId(sectionId, `project.visual_contract.required_sections[${index}]`))
  if (new Set(requiredSections).size !== requiredSections.length) {
    throw new TypeError('project.visual_contract.required_sections must be unique')
  }
  for (const sectionId of requiredSections) {
    if (!ids.includes(sectionId)) throw new TypeError(`visual required section is not planned: ${sectionId}`)
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
    const purpose = requireText(raw.purpose, `project.visual_contract.figures[${index}].purpose`)
    return {
      id: requireSafeId(raw.id, `project.visual_contract.figures[${index}].id`),
      number: requirePositiveInteger(
        raw.number,
        `project.visual_contract.figures[${index}].number`,
        figureStart + index,
      ),
      section_id: sectionId,
      kind: requireText(raw.kind, `project.visual_contract.figures[${index}].kind`),
      purpose,
      required_labels: requiredLabels,
      review_required: raw.review_required !== false,
      design_brief: normalizeDesignBrief(raw.design_brief, {
        purpose,
        strict: visualSchemaVersion === 2,
        name: `project.visual_contract.figures[${index}].design_brief`,
      }),
    }
  })
  const visualIds = visualFigures.map(figure => figure.id)
  if (new Set(visualIds).size !== visualIds.length) {
    throw new TypeError('project.visual_contract.figure ids must be unique')
  }
  const visualNumbers = visualFigures.map(figure => figure.number)
  if (new Set(visualNumbers).size !== visualNumbers.length) {
    throw new TypeError('project.visual_contract.figure numbers must be unique')
  }
  const expectedVisualNumbers = visualFigures.map((_, index) => figureStart + index)
  if (visualNumbers.some((number, index) => number !== expectedVisualNumbers[index])) {
    throw new TypeError(`project.visual_contract.figure numbers must be contiguous from ${figureStart}`)
  }

  const quality = isPlainObject(input.quality_contract) ? input.quality_contract : {}
  const minimumSectionRatio = requireRatio(
    quality.minimum_section_ratio,
    'project.quality_contract.minimum_section_ratio',
    0.75,
  )
  const minimumTotalRatio = requireRatio(
    quality.minimum_total_ratio,
    'project.quality_contract.minimum_total_ratio',
    0.75,
  )
  const maximumSectionRatio = requireUpperRatio(
    quality.maximum_section_ratio,
    'project.quality_contract.maximum_section_ratio',
    4,
  )
  const maximumTotalRatio = requireUpperRatio(
    quality.maximum_total_ratio,
    'project.quality_contract.maximum_total_ratio',
    4,
  )
  if (maximumSectionRatio < minimumSectionRatio) {
    throw new TypeError('project.quality_contract.maximum_section_ratio must be >= minimum_section_ratio')
  }
  if (maximumTotalRatio < minimumTotalRatio) {
    throw new TypeError('project.quality_contract.maximum_total_ratio must be >= minimum_total_ratio')
  }
  const research = isPlainObject(input.research_contract) ? input.research_contract : {}
  return {
    schema_version: 1,
    title: requireText(input.title, 'project.title'),
    objective: requireText(input.objective, 'project.objective'),
    audience: requireText(input.audience ?? 'general technical readers', 'project.audience'),
    language: requireText(input.language ?? 'zh-CN', 'project.language'),
    mode: 'markdown',
    sections,
    visual_contract: {
      schema_version: visualSchemaVersion,
      figure_start: figureStart,
      minimum_figures: minimumFigures,
      required_sections: requiredSections,
      figures: visualFigures,
    },
    quality_contract: {
      minimum_section_ratio: minimumSectionRatio,
      maximum_section_ratio: maximumSectionRatio,
      minimum_total_ratio: minimumTotalRatio,
      maximum_total_ratio: maximumTotalRatio,
      long_sentence_chars: Math.min(500, requirePositiveInteger(
        quality.long_sentence_chars,
        'project.quality_contract.long_sentence_chars',
        80,
      )),
      maximum_long_sentence_ratio: requireUnitRatio(
        quality.maximum_long_sentence_ratio,
        'project.quality_contract.maximum_long_sentence_ratio',
        1,
      ),
      minimum_review_score: Math.min(100, requirePositiveInteger(
        quality.minimum_review_score,
        'project.quality_contract.minimum_review_score',
        85,
      )),
      require_zero_placeholders: quality.require_zero_placeholders !== false,
      require_review: quality.require_review !== false,
    },
    research_contract: {
      minimum_image_searches: requireNonNegativeInteger(
        research.minimum_image_searches,
        'project.research_contract.minimum_image_searches',
      ),
      minimum_image_candidates: requireNonNegativeInteger(
        research.minimum_image_candidates,
        'project.research_contract.minimum_image_candidates',
      ),
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
    image_searches: [],
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
    if (!isPlainObject(visualContract)) throw new TypeError('visual_contract must be an object')
    const mergedContract = {
      ...visualContract,
      schema_version: project.visual_contract.schema_version,
      figure_start: project.visual_contract.figure_start,
      minimum_figures: project.visual_contract.minimum_figures,
      required_sections: project.visual_contract.required_sections,
    }
    const normalized = normalizeProject({ ...project, visual_contract: mergedContract })
    const planned = normalized.visual_contract.figures
    if (planned.length < normalized.visual_contract.minimum_figures) {
      throw new Error(`visual contract requires at least ${normalized.visual_contract.minimum_figures} figures`)
    }
    const plannedSections = new Set(planned.map(figure => figure.section_id))
    const missingSections = normalized.visual_contract.required_sections.filter(sectionId => !plannedSections.has(sectionId))
    if (missingSections.length > 0) {
      throw new Error(`visual contract does not cover required sections: ${missingSections.join(', ')}`)
    }
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
  if (!Array.isArray(raw.image_searches)) raw.image_searches = []
  return raw
}

function boundedSearchText(value, name, maximum = 4096) {
  const text = requireText(value, name)
  if (text.length > maximum) throw new TypeError(`${name} is too long`)
  return text
}

function optionalSearchText(value, name, maximum = 4096) {
  if (value === undefined || value === null || value === '') return null
  return boundedSearchText(value, name, maximum)
}

function publicHttpUrl(value, name) {
  const text = boundedSearchText(value, name)
  let url
  try {
    url = new URL(text)
  } catch {
    throw new TypeError(`${name} must be an absolute HTTP(S) URL`)
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new TypeError(`${name} must be an absolute HTTP(S) URL`)
  }
  return url.toString()
}

/**
 * Append a compact, immutable receipt for one successful image-search result.
 * The host calls this directly from the real search response, so the model
 * cannot fabricate a claim that image discovery happened.
 */
export async function appendImageSearchReceipt(workspace, result) {
  const root = resolveWorkspace(workspace)
  if (!isPlainObject(result) || result.status !== 'ok') {
    throw new TypeError('image search receipt requires a successful search response')
  }
  if (!Array.isArray(result.results)) throw new TypeError('image search results must be an array')
  const candidates = result.results.slice(0, 20).map((raw, index) => {
    if (!isPlainObject(raw)) throw new TypeError(`image search result ${index} must be an object`)
    const width = raw.width === undefined || raw.width === null
      ? null
      : requirePositiveInteger(raw.width, `image search result ${index}.width`)
    const height = raw.height === undefined || raw.height === null
      ? null
      : requirePositiveInteger(raw.height, `image search result ${index}.height`)
    const score = requireNonNegativeInteger(raw.score, `image search result ${index}.score`)
    if (score > 100) throw new TypeError(`image search result ${index}.score must be <= 100`)
    return {
      source_id: boundedSearchText(raw.source_id, `image search result ${index}.source_id`, 200),
      rank: requirePositiveInteger(raw.rank, `image search result ${index}.rank`),
      title: optionalSearchText(raw.title, `image search result ${index}.title`, 1000),
      image_url: publicHttpUrl(raw.murl, `image search result ${index}.murl`),
      source_page_url: raw.purl ? publicHttpUrl(raw.purl, `image search result ${index}.purl`) : null,
      width,
      height,
      score,
      domain_hint: ['good', 'neutral', 'bad'].includes(raw.domain_hint) ? raw.domain_hint : 'neutral',
    }
  })
  const payload = {
    query: boundedSearchText(result.query, 'image search query', 1000),
    provider: boundedSearchText(result.provider, 'image search provider', 80),
    candidates,
  }
  const receipt = {
    id: `image-search-${randomUUID()}`,
    ...payload,
    result_sha256: createHash('sha256').update(JSON.stringify(payload), 'utf8').digest('hex'),
    searched_at: new Date().toISOString(),
  }
  return withWorkspaceLock(root, async () => {
    const manifest = await readAssetManifest(root)
    manifest.image_searches.push(receipt)
    await atomicWrite(path.join(root, ASSET_MANIFEST_FILENAME), `${JSON.stringify(manifest, null, 2)}\n`)
    return receipt
  })
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
    if (derivativeOf !== undefined) {
      if (derivativeOf.asset_id === id) throw new Error('asset derivative_of must not reference itself')
      const parent = findAssetById(manifest, derivativeOf.asset_id)
      if (!parent) throw new Error(`asset derivative parent is not registered: ${derivativeOf.asset_id}`)
      if (parent.sha256 !== derivativeOf.asset_sha256) {
        throw new Error(`asset derivative parent hash does not match the manifest: ${derivativeOf.asset_id}`)
      }
    }
    if (visualPlanId !== undefined) {
      const plan = await resolveVisualPlan(root, visualPlanId)
      if (plan.kind === 'photo') {
        const ext = path.extname(rel).toLowerCase()
        if (!rel.startsWith('assets/photos/') || !['.png', '.jpg', '.jpeg', '.webp'].includes(ext)) {
          throw new Error('a photo visual_plan_id may be bound only to an assets/photos/* raster')
        }
      } else if (!rel.startsWith('assets/svg/') || !rel.endsWith('.svg')) {
        throw new Error('a visual_plan_id may be bound only to an assets/svg/*.svg asset')
      }
      const plannedAssets = manifest.assets.filter(entry => entry && entry.visual_plan_id === plan.id)
      if (plannedAssets.length > 0) {
        if (!supersedesAssetId) {
          throw new Error(`a new revision for visual plan ${plan.id} requires supersedes_asset_id`)
        }
        const predecessor = plannedAssets.find(entry => entry.id === supersedesAssetId)
        if (!predecessor) {
          throw new Error('supersedes_asset_id must name an asset bound to the same visual plan')
        }
        if (plannedAssets.some(entry => entry.supersedes_asset_id === predecessor.id)) {
          throw new Error(`supersedes_asset_id already has a successor: ${predecessor.id}`)
        }
      } else if (supersedesAssetId !== undefined) {
        throw new Error('the first asset for a visual plan must not declare supersedes_asset_id')
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

function receiptObject(value, name, { maximum = 20_000 } = {}) {
  if (!isPlainObject(value)) throw new TypeError(`${name} must be an object`)
  const serialized = JSON.stringify(value)
  if (serialized.length > maximum) throw new TypeError(`${name} is too large`)
  return JSON.parse(serialized)
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
      throw new Error('preflight visual_plan_id does not match the registered planned asset')
    }
    const expectedPreview = plan.kind === 'photo' ? 'photo-preview' : 'svg-preview'
    const derivative = preview.entry.derivative_of
    if (!isPlainObject(derivative)
      || derivative.asset_id !== assetId
      || derivative.asset_sha256 !== assetSha
      || derivative.purpose !== expectedPreview) {
      throw new Error(`preflight preview must be a registered ${expectedPreview} derivative of the planned asset`)
    }
    if (plan.kind === 'photo' && !asset.entry.path.startsWith('assets/photos/')) {
      throw new Error('photo preflight asset must live under assets/photos/')
    }
    if (plan.kind !== 'photo' && (!asset.entry.path.startsWith('assets/svg/') || !asset.entry.path.endsWith('.svg'))) {
      throw new Error('diagram preflight asset must be a registered assets/svg/*.svg file')
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
      ...(input.design_metrics === undefined
        ? {}
        : { design_metrics: receiptObject(input.design_metrics, 'preflight design_metrics') }),
      created_at: new Date().toISOString(),
    }
    manifest.visual_preflights.push(receipt)
    await atomicWrite(path.join(root, ASSET_MANIFEST_FILENAME), `${JSON.stringify(manifest, null, 2)}\n`)
    return receipt
  })
}

/** Append an identity-labelled inspection receipt for a retained PNG preview. */
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
    const expectedPreviewPurpose = plan.kind === 'photo' ? 'photo-preview' : 'svg-preview'
    if (!isPlainObject(derivative)
      || derivative.asset_id !== assetId
      || derivative.asset_sha256 !== preflight.asset_sha256
      || derivative.purpose !== expectedPreviewPurpose) {
      throw new Error('review preview no longer binds to the reviewed planned asset')
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
    const reviewerRole = receiptText(input.reviewer_role, 'review reviewer_role', { maximum: 80 })
    if (!['author_visual_check', 'independent_visual_review', 'human_visual_review'].includes(reviewerRole)) {
      throw new TypeError('review reviewer_role is not recognized')
    }
    if (reviewerRole === 'independent_visual_review' && !Array.isArray(input.scientific_checks)) {
      throw new TypeError('independent visual review requires structured scientific_checks')
    }
    const rawScientificChecks = input.scientific_checks ?? plan.design_brief.scientific_checks.map(criterion => ({
      criterion,
      verdict,
      evidence: input.summary,
    }))
    if (!Array.isArray(rawScientificChecks) || rawScientificChecks.length !== plan.design_brief.scientific_checks.length) {
      throw new TypeError('review scientific_checks must match the planned scientific criteria')
    }
    const scientificChecks = rawScientificChecks.map((item, index) => {
      if (!isPlainObject(item)) throw new TypeError(`review scientific_checks[${index}] must be an object`)
      const criterion = receiptText(item.criterion, `review scientific_checks[${index}].criterion`, { maximum: 800 })
      if (criterion !== plan.design_brief.scientific_checks[index]) {
        throw new Error(`review scientific_checks[${index}] does not match the planned criterion`)
      }
      const checkVerdict = receiptText(item.verdict, `review scientific_checks[${index}].verdict`, { maximum: 10 })
      if (checkVerdict !== 'pass' && checkVerdict !== 'fail') {
        throw new TypeError(`review scientific_checks[${index}].verdict must be pass or fail`)
      }
      return {
        criterion,
        verdict: checkVerdict,
        evidence: receiptText(item.evidence, `review scientific_checks[${index}].evidence`, { maximum: 1000 }),
      }
    })
    if (reviewerRole === 'independent_visual_review' && !isPlainObject(input.design_checks)) {
      throw new TypeError('independent visual review requires structured design_checks')
    }
    const rawDesignChecks = input.design_checks ?? Object.fromEntries(DESIGN_CHECK_KEYS.map(key => [key, verdict]))
    if (!isPlainObject(rawDesignChecks)
      || Object.keys(rawDesignChecks).length !== DESIGN_CHECK_KEYS.length
      || DESIGN_CHECK_KEYS.some(key => !Object.hasOwn(rawDesignChecks, key))) {
      throw new TypeError('review design_checks must contain the complete design rubric')
    }
    const designChecks = Object.fromEntries(DESIGN_CHECK_KEYS.map(key => {
      const checkVerdict = receiptText(rawDesignChecks[key], `review design_checks.${key}`, { maximum: 10 })
      if (checkVerdict !== 'pass' && checkVerdict !== 'fail') {
        throw new TypeError(`review design_checks.${key} must be pass or fail`)
      }
      return [key, checkVerdict]
    }))
    if (verdict === 'pass' && scientificChecks.some(item => item.verdict !== 'pass')) {
      throw new Error('a passing review requires every scientific check to pass')
    }
    if (verdict === 'pass' && DESIGN_CHECK_KEYS.some(key => designChecks[key] !== 'pass')) {
      throw new Error('a passing review requires every design check to pass')
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
      reviewer_role: reviewerRole,
      verdict,
      summary: receiptText(input.summary, 'review summary', { maximum: 4000 }),
      findings: receiptTextArray(input.findings, 'review findings'),
      checked_labels: checkedLabels,
      scientific_checks: scientificChecks,
      design_checks: designChecks,
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
    if (project.visual_contract.figures.length < project.visual_contract.minimum_figures) {
      throw new Error('complete the required visual plan before committing manuscript prose')
    }
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

export function sentenceStats(text, longSentenceChars = 80) {
  const prose = String(text ?? '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/^\s*[#>|-]+\s*/gm, '')
  const sentences = prose
    .split(/(?<=[。！？!?；;])|(?<!\d)\.(?!\d)|\n+/u)
    .map(value => value.replace(/\s+/g, '').trim())
    .filter(value => /[\p{L}\p{N}\u3400-\u9FFF]/u.test(value))
  const lengths = sentences.map(value => [...value].length)
  const longCount = lengths.filter(length => length > longSentenceChars).length
  return {
    sentence_count: sentences.length,
    long_sentence_count: longCount,
    long_sentence_ratio: sentences.length === 0 ? 0 : Number((longCount / sentences.length).toFixed(3)),
    maximum_sentence_chars: lengths.length === 0 ? 0 : Math.max(...lengths),
  }
}

export async function publicationStatus(workspace) {
  const root = resolveWorkspace(workspace)
  const [project, article] = await Promise.all([readProject(root), readArticle(root)])
  const chunks = parseChunks(article)
  const sections = project.sections.map(section => {
    const prose = sectionText(article, section.id)
    const wordCount = countWords(prose)
    const sectionChunks = chunks.filter(chunk => chunk.section_id === section.id).map(chunk => chunk.id)
    return {
      id: section.id,
      title: section.title,
      target_words: section.target_words,
      word_count: wordCount,
      completion_ratio: Number((wordCount / section.target_words).toFixed(3)),
      chunk_ids: sectionChunks,
      ...sentenceStats(prose, project.quality_contract.long_sentence_chars),
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
