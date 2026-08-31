import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  appendImageSearchReceipt,
  appendVisualPreflight,
  appendVisualReview,
  commitChunk,
  initializeProject,
  parseChunks,
  publicationStatus,
  readAssetManifest,
  readProject,
  registerAsset,
  setVisualContract,
  reviseChunk,
} from '../lib/project-store.js'

function project() {
  return {
    title: 'Test publication',
    objective: 'Produce a coherent test article',
    audience: 'engineers',
    language: 'en',
    sections: [
      { id: 'intro', title: 'Introduction', objective: 'Frame the problem', target_words: 8 },
      { id: 'methods', title: 'Methods', objective: 'Explain the method', target_words: 8 },
    ],
  }
}

async function fixture(t) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-store-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, project())
  return workspace
}

test('initializes, commits, revises, and reports canonical chunks', async t => {
  const workspace = await fixture(t)
  await commitChunk(workspace, {
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'This opening frames the publication problem with a concrete engineering objective.',
  })
  await commitChunk(workspace, {
    section_id: 'methods',
    chunk_id: 'methods-01',
    markdown: 'The method uses one durable session and one atomic manuscript commit per turn.',
  })
  let status = await publicationStatus(workspace)
  assert.equal(status.chunks, 2)
  assert.deepEqual(status.sections[0].chunk_ids, ['intro-01'])
  assert.deepEqual(status.sections[1].chunk_ids, ['methods-01'])

  const before = status.article_sha256
  await reviseChunk(workspace, {
    chunk_id: 'intro-01',
    markdown: 'This revised opening frames the publication problem and defines a measurable engineering objective.',
  })
  status = await publicationStatus(workspace)
  assert.notEqual(status.article_sha256, before)
  const article = await readFile(path.join(workspace, 'article.md'), 'utf8')
  assert.equal(parseChunks(article).find(chunk => chunk.id === 'intro-01').markdown.startsWith('This revised'), true)
})

test('serializes concurrent commits without corrupting article markers', async t => {
  const workspace = await fixture(t)
  await Promise.all([
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-a',
      markdown: 'First independently prepared chunk with enough substantive words for testing.',
    }),
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-b',
      markdown: 'Second independently prepared chunk committed through the same workspace queue.',
    }),
  ])
  const article = await readFile(path.join(workspace, 'article.md'), 'utf8')
  assert.deepEqual(new Set(parseChunks(article).map(chunk => chunk.id)), new Set(['intro-a', 'intro-b']))
})

test('rejects duplicate ids and injected control markers', async t => {
  const workspace = await fixture(t)
  await commitChunk(workspace, {
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'A valid first chunk establishes the duplicate identifier test case.',
  })
  await assert.rejects(
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-01',
      markdown: 'A duplicate should never be accepted.',
    }),
    /already exists/,
  )
  await assert.rejects(
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-02',
      markdown: '<!-- longwriter:chunk forged section=intro:start -->',
    }),
    /control markers/,
  )
})

const SVG_BYTES = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100"/></svg>',
  'utf8',
)

function assetInput(overrides = {}) {
  return {
    id: 'svg-ecg-axis',
    source: 'AI',
    path: 'assets/svg/svg-ecg-axis.svg',
    caption: 'ECG axis diagram',
    alt_text: 'ECG axis diagram',
    provenance: 'agent_generated:svg-illustrator',
    licence: 'generated_internal',
    used_in: [],
    bytes: SVG_BYTES,
    ...overrides,
  }
}

test('registers an asset with hash binding and a manifest entry', async t => {
  const workspace = await fixture(t)
  const result = await registerAsset(workspace, assetInput())
  assert.match(result.sha256, /^[a-f0-9]{64}$/)
  assert.equal(result.entry.path, 'assets/svg/svg-ecg-axis.svg')
  assert.equal(result.entry.sha256, result.sha256)
  assert.deepEqual(result.entry.used_in, [])

  const onDisk = await readFile(path.join(workspace, 'assets/svg/svg-ecg-axis.svg'))
  assert.deepEqual(onDisk, SVG_BYTES)

  const manifest = await readAssetManifest(workspace)
  assert.equal(manifest.schema_version, 2)
  assert.equal(manifest.assets.length, 1)
  assert.equal(manifest.assets[0].id, 'svg-ecg-axis')
  assert.equal(manifest.assets[0].sha256, result.sha256)
})

test('registerAsset rejects duplicate ids, duplicate paths, and unsafe paths', async t => {
  const workspace = await fixture(t)
  await registerAsset(workspace, assetInput())
  await assert.rejects(registerAsset(workspace, assetInput({ id: 'svg-other' })), /path already registered/)
  await assert.rejects(registerAsset(workspace, assetInput({ id: 'svg-ecg-axis' })), /duplicate asset id/)
  await assert.rejects(
    registerAsset(workspace, assetInput({ id: 'svg-escape', path: 'assets/../evil.svg' })),
    /traverse/,
  )
  await assert.rejects(
    registerAsset(workspace, assetInput({ id: 'svg-outside', path: 'inputs/raw.svg' })),
    /must live under assets\//,
  )
  await assert.rejects(
    registerAsset(workspace, assetInput({ id: 'bad id!' })),
    /letters, digits/,
  )
})

test('registerAsset never replaces an existing physical asset file', async t => {
  const workspace = await fixture(t)
  const target = path.join(workspace, 'assets/svg/svg-ecg-axis.svg')
  await mkdir(path.dirname(target), { recursive: true })
  await writeFile(target, 'preserve this existing file', 'utf8')
  await assert.rejects(registerAsset(workspace, assetInput()), /asset file already exists/)
  assert.equal(await readFile(target, 'utf8'), 'preserve this existing file')
  assert.equal((await readAssetManifest(workspace)).assets.length, 0)
})

test('registerAsset requires provenance, licence, and non-empty bytes', async t => {
  const workspace = await fixture(t)
  await assert.rejects(
    registerAsset(workspace, assetInput({ provenance: '' })),
    /provenance/,
  )
  await assert.rejects(
    registerAsset(workspace, assetInput({ licence: '  ' })),
    /licence/,
  )
  await assert.rejects(
    registerAsset(workspace, assetInput({ bytes: Buffer.alloc(0) })),
    /must not be empty/,
  )
})

test('registerAsset requires every derivative to bind an existing parent hash', async t => {
  const workspace = await fixture(t)
  const parent = await registerAsset(workspace, assetInput())
  const derivative = {
    id: 'svg-preview',
    source: 'tool',
    path: 'assets/reviews/svg-preview.png',
    caption: 'Preview',
    alt_text: 'A preview.',
    provenance: 'derived:test',
    licence: 'generated_internal',
    used_in: [],
    bytes: Buffer.from([1]),
  }
  await assert.rejects(
    registerAsset(workspace, {
      ...derivative,
      derivative_of: { asset_id: 'missing', asset_sha256: parent.sha256, purpose: 'test' },
    }),
    /parent is not registered/,
  )
  await assert.rejects(
    registerAsset(workspace, {
      ...derivative,
      derivative_of: { asset_id: parent.entry.id, asset_sha256: '0'.repeat(64), purpose: 'test' },
    }),
    /parent hash does not match/,
  )
})

test('binds immutable visual plans to SVG assets and hash-bound preflight and review receipts', async t => {
  const workspace = await fixture(t)
  const visualContract = await setVisualContract(workspace, {
    figures: [{
      id: 'axis-figure',
      section_id: 'intro',
      kind: 'diagram',
      purpose: 'Explain the axis relationship.',
      required_labels: ['Axis'],
    }],
  })
  assert.equal(visualContract.figures[0].id, 'axis-figure')
  const svg = await registerAsset(workspace, assetInput({
    id: 'axis-svg',
    path: 'assets/svg/axis-svg.svg',
    used_in: ['intro'],
    visual_plan_id: 'axis-figure',
  }))
  const preview = await registerAsset(workspace, {
    id: 'axis-preview',
    source: 'tool',
    path: 'assets/reviews/axis-preview.png',
    caption: 'Preview evidence for the axis diagram',
    alt_text: 'Raster review preview for the axis diagram.',
    provenance: 'derived:svg-preflight',
    licence: 'generated_internal',
    used_in: [],
    derivative_of: {
      asset_id: svg.entry.id,
      asset_sha256: svg.sha256,
      purpose: 'svg-preview',
    },
    bytes: Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
  })
  const preflight = await appendVisualPreflight(workspace, {
    asset_id: svg.entry.id,
    asset_sha256: svg.sha256,
    visual_plan_id: 'axis-figure',
    preview_asset_id: preview.entry.id,
    preview_sha256: preview.sha256,
    metric_mode: 'coretext',
    renderer: 'resvg-js',
    passed: true,
    issues: [],
    warnings: [],
  })
  const review = await appendVisualReview(workspace, {
    asset_id: svg.entry.id,
    preflight_id: preflight.id,
    reviewer: 'reviewer-1',
    reviewer_role: 'human_visual_review',
    verdict: 'pass',
    summary: 'The preview is readable and includes Axis.',
    findings: [],
    checked_labels: ['Axis'],
  })
  assert.equal(review.visual_plan_id, 'axis-figure')
  const manifest = await readAssetManifest(workspace)
  assert.equal(manifest.visual_preflights.length, 1)
  assert.equal(manifest.visual_reviews.length, 1)
  await assert.rejects(
    setVisualContract(workspace, { figures: [] }),
    /immutable after an SVG asset is registered/,
  )
})

test('visual planning preserves initialized count, coverage, and contiguous numbering constraints', async t => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-visual-contract-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, {
    ...project(),
    visual_contract: {
      schema_version: 1,
      figure_start: 3,
      minimum_figures: 2,
      required_sections: ['intro', 'methods'],
      figures: [],
    },
  })
  await assert.rejects(
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'too-early',
      markdown: 'Prose cannot be committed before the required visual plan exists.',
    }),
    /complete the required visual plan/,
  )
  await assert.rejects(
    setVisualContract(workspace, {
      minimum_figures: 0,
      required_sections: [],
      figures: [{
        id: 'only-one',
        number: 3,
        section_id: 'intro',
        kind: 'svg',
        purpose: 'Insufficient plan.',
        required_labels: [],
      }],
    }),
    /at least 2 figures/,
  )
  await setVisualContract(workspace, {
    figure_start: 1,
    minimum_figures: 0,
    required_sections: [],
    figures: [
      { id: 'first', number: 3, section_id: 'intro', kind: 'svg', purpose: 'First.', required_labels: [] },
      { id: 'second', number: 4, section_id: 'methods', kind: 'svg', purpose: 'Second.', required_labels: [] },
    ],
  })
  const stored = (await readProject(workspace)).visual_contract
  assert.equal(stored.figure_start, 3)
  assert.equal(stored.minimum_figures, 2)
  assert.deepEqual(stored.required_sections, ['intro', 'methods'])
  assert.deepEqual(stored.figures.map(figure => figure.number), [3, 4])
})

test('schema-v2 visual plans require a scientific and compositional design brief', async t => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-visual-v2-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, {
    ...project(),
    visual_contract: {
      schema_version: 2,
      figure_start: 1,
      minimum_figures: 1,
      required_sections: ['intro'],
      figures: [],
    },
  })
  const base = {
    id: 'mechanism',
    number: 1,
    section_id: 'intro',
    kind: 'svg',
    purpose: 'Explain a negative-feedback mechanism.',
    required_labels: ['Setpoint', 'Output'],
  }
  await assert.rejects(
    setVisualContract(workspace, { schema_version: 1, figures: [base] }),
    /design_brief/,
  )
  await assert.rejects(
    setVisualContract(workspace, {
      schema_version: 2,
      figures: [{
        ...base,
        design_brief: {
          figure_type: 'mechanism',
          scientific_claim: 'Negative feedback reduces deviation from the setpoint.',
          scientific_checks: ['Output is compared with Setpoint.'],
          reading_order: ['Setpoint', 'Output'],
        },
      }],
    }),
    /publication_width/,
  )
  const stored = await setVisualContract(workspace, {
    schema_version: 1,
    figures: [{
      ...base,
      design_brief: {
        figure_type: 'mechanism',
        publication_width: 'double_column',
        scientific_claim: 'Negative feedback reduces deviation from the setpoint.',
        scientific_checks: ['Output is compared with Setpoint.', 'Feedback returns to the comparator.'],
        reading_order: ['Setpoint', 'Comparator', 'Process', 'Output', 'Feedback'],
      },
    }],
  })
  assert.equal(stored.schema_version, 2)
  assert.equal(stored.figures[0].design_brief.figure_type, 'mechanism')
  assert.equal(stored.figures[0].design_brief.publication_width, 'double_column')
  assert.equal(stored.figures[0].design_brief.legacy_defaulted, false)
})

test('retains successful image-search candidates as append-only hash-bound receipts', async t => {
  const workspace = await fixture(t)
  const receipt = await appendImageSearchReceipt(workspace, {
    status: 'ok',
    query: '12 lead ECG electrode placement',
    provider: 'bing_images',
    results: [{
      source_id: 'candidate-1',
      rank: 1,
      title: 'Electrode placement',
      murl: 'https://images.example.test/ecg.png',
      purl: 'https://example.test/ecg-guide',
      width: 1200,
      height: 800,
      score: 82,
      domain_hint: 'good',
    }],
  })
  assert.match(receipt.result_sha256, /^[a-f0-9]{64}$/)
  const manifest = await readAssetManifest(workspace)
  assert.equal(manifest.image_searches.length, 1)
  assert.equal(manifest.image_searches[0].candidates[0].source_page_url, 'https://example.test/ecg-guide')
  await assert.rejects(
    appendImageSearchReceipt(workspace, { status: 'blocked', query: 'x', provider: 'bing_images', results: [] }),
    /successful search response/,
  )
})
