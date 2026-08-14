import { createHash, randomUUID } from 'node:crypto'
import { mkdir, open, readFile, rename, stat, unlink } from 'node:fs/promises'
import path from 'node:path'

export const PROJECT_FILENAME = 'project.json'
export const ARTICLE_FILENAME = 'article.md'
export const ASSET_MANIFEST_FILENAME = 'assets/manifest.json'

const SAFE_ID = /^[A-Za-z0-9_-]+$/
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

  const quality = isPlainObject(input.quality_contract) ? input.quality_contract : {}
  return {
    schema_version: 1,
    title: requireText(input.title, 'project.title'),
    objective: requireText(input.objective, 'project.objective'),
    audience: requireText(input.audience ?? 'general technical readers', 'project.audience'),
    language: requireText(input.language ?? 'zh-CN', 'project.language'),
    mode: 'markdown',
    sections,
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

export async function readArticle(workspace) {
  const root = resolveWorkspace(workspace)
  return readFile(path.join(root, ARTICLE_FILENAME), 'utf8')
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
