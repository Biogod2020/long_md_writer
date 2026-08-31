import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  SvgJobManager,
  SVG_WORKER_OUTPUT_SCHEMA,
  SVG_WORKER_REVISION_OUTPUT_SCHEMA,
  candidateFitness,
  compareFitness,
  lockRegressions,
} from '../app-server/svg-job-manager.js'
import { DESIGN_CHECK_KEYS } from '../svg/design.js'
import { initializeProject, setVisualContract } from '../lib/project-store.js'

function project() {
  return {
    title: 'Async SVG test',
    objective: 'Verify bounded SVG delegation.',
    audience: 'students',
    language: 'English',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain the mechanism.', target_words: 20 }],
    visual_contract: {
      schema_version: 2,
      figure_start: 1,
      minimum_figures: 1,
      required_sections: ['intro'],
      figures: [],
    },
    quality_contract: {
      minimum_section_ratio: 0.75,
      maximum_section_ratio: 1.3,
      minimum_total_ratio: 0.75,
      maximum_total_ratio: 1.3,
      long_sentence_chars: 80,
      maximum_long_sentence_ratio: 1,
      minimum_review_score: 85,
    },
    research_contract: { minimum_image_searches: 0, minimum_image_candidates: 0 },
  }
}

async function workspaceFixture(t, figureCount = 1) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-svg-jobs-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, project())
  await setVisualContract(workspace, {
    schema_version: 2,
    figure_start: 1,
    minimum_figures: 1,
    required_sections: ['intro'],
    figures: Array.from({ length: figureCount }, (_, index) => ({
      id: index === 0 ? 'mechanism' : `mechanism-${index + 1}`,
      number: index + 1,
      section_id: 'intro',
      kind: 'svg',
      purpose: 'Show signal flow from input to output.',
      required_labels: ['Input', 'Output'],
      review_required: true,
      design_brief: {
        figure_type: 'mechanism',
        publication_width: 'double_column',
        scientific_claim: 'The input reaches the output through one directed transformation.',
        scientific_checks: ['Input connects to Output.', 'Every arrow points toward Output.'],
        reading_order: ['Read Input first.', 'Follow the arrow to Output.'],
      },
    })),
  })
  return workspace
}

function review({
  verdict = 'fail',
  scientific = ['pass', 'fail'],
  failedDesign = ['reading_order'],
  finding = 'Correct the remaining directed connection.',
} = {}) {
  return {
    receipt: {
      id: `review-${scientific.join('-')}-${failedDesign.join('-') || 'none'}`,
      verdict,
      summary: verdict === 'pass' ? 'Everything passes.' : 'The reading order is incomplete.',
      findings: verdict === 'pass' ? [] : [finding],
      checked_labels: ['Input', 'Output'],
      scientific_checks: [
        { criterion: 'Input connects to Output.', verdict: scientific[0], evidence: 'Visible.' },
        { criterion: 'Every arrow points toward Output.', verdict: scientific[1], evidence: 'Visible.' },
      ],
      design_checks: Object.fromEntries(DESIGN_CHECK_KEYS.map(key => [key, failedDesign.includes(key) ? 'fail' : 'pass'])),
    },
  }
}

function evaluation(assetId, reviewResult, issues = []) {
  return {
    submission: { registered: true, score: 90 },
    preflight: {
      status: issues.length === 0 ? 'passed' : 'failed',
      preflight_id: `preflight-${assetId}`,
      report: {
        issues,
        required_labels: [
          { label: 'Input', present: true },
          { label: 'Output', present: true },
        ],
      },
    },
    ...(issues.length === 0 ? { review: reviewResult } : {}),
    asset_id: assetId,
    asset_path: `assets/svg/${assetId}.svg`,
    asset_sha256: assetId.padEnd(64, 'a').slice(0, 64),
  }
}

async function waitForTerminal(manager, jobId) {
  for (let index = 0; index < 30; index += 1) {
    const current = manager.status(jobId).job
    if (current.status === 'passed' || current.status === 'failed') return current
    await manager.wait(jobId, 1000)
  }
  throw new Error('SVG job did not reach a terminal status')
}

test('fitness ranks independent visual evidence above geometry-only candidates', () => {
  const geometryOnly = candidateFitness(evaluation('geometry', null, ['text_overlap']))
  const reviewed = candidateFitness(evaluation('reviewed', review()))
  const passed = candidateFitness(evaluation('passed', review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] })))
  assert.ok(compareFitness(reviewed, geometryOnly) > 0)
  assert.ok(compareFitness(passed, reviewed) > 0)
})

test('pixel diagnostic findings are prioritized in the next local-edit prompt without granting a pass', async t => {
  const workspace = await workspaceFixture(t)
  const sources = new Map()
  const prompts = []
  let candidateIndex = 0
  const candidates = [
    { svg: '<svg>diagnosed</svg>', caption: 'Diagnosed', alt_text: 'Diagnosed', change_summary: 'Initial.' },
    { svg: '<svg>passing</svg>', caption: 'Passing', alt_text: 'Passing', change_summary: 'Fixed.' },
  ]
  const first = evaluation('asset-diagnosed', null, [
    'text_below_minimum_font_size:0:"Input":12.00<25.84',
    'text_overlap:0:"Input":1:"Output"',
  ])
  first.diagnostic = {
    status: 'diagnosed_fail',
    review: {
      verdict: 'fail',
      summary: 'The rendered labels collide in the center lane.',
      findings: ['Move Output into the empty right lane and keep both labels large.'],
      scientific_checks: [
        { criterion: 'Input connects to Output.', verdict: 'pass' },
        { criterion: 'Every arrow points toward Output.', verdict: 'fail' },
      ],
      design_checks: Object.fromEntries(DESIGN_CHECK_KEYS.map(key => [key, key === 'composition_spacing' ? 'fail' : 'pass'])),
    },
  }
  const second = evaluation('asset-passing', review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] }))
  const evaluations = [first, second]
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 1,
    maxAttempts: 2,
    startWorker: async () => `diagnostic-worker-${candidateIndex + 1}`,
    runWorker: async ({ prompt }) => {
      prompts.push(prompt)
      return candidates[candidateIndex]
    },
    processCandidate: async ({ candidate }) => {
      const current = evaluations[candidateIndex]
      sources.set(current.asset_id, candidate.svg)
      candidateIndex += 1
      return current
    },
    readRegisteredAsset: async (_workspace, assetId) => ({
      entry: { id: assetId, caption: assetId, alt_text: assetId, path: `assets/svg/${assetId}.svg`, visual_plan_id: 'mechanism' },
      bytes: Buffer.from(sources.get(assetId)),
      sha256: assetId.padEnd(64, 'a').slice(0, 64),
    }),
  })

  const delegated = await manager.delegate('mechanism')
  const completed = await waitForTerminal(manager, delegated.job.id)
  await manager.stop()

  assert.equal(completed.status, 'passed')
  assert.equal(completed.attempts, 2)
  assert.equal(completed.best.asset_id, 'asset-passing')
  assert.match(prompts[1], /visual diagnosis: The rendered labels collide in the center lane/)
  assert.match(prompts[1], /visual finding: Move Output into the empty right lane/)
  assert.match(prompts[1], /12\.00<25\.84/)
  assert.match(prompts[1], /rather than smaller text/)
})

test('champion baseline rejects regressed locks and fresh workers converge without oscillating', async t => {
  const workspace = await workspaceFixture(t)
  const candidates = [
    { svg: '<svg>candidate-one</svg>', caption: 'One', alt_text: 'One', change_summary: 'Initial.' },
    { svg: '<svg>candidate-two</svg>', caption: 'Two', alt_text: 'Two', change_summary: 'Regresses an old pass.' },
    { svg: '<svg>candidate-three</svg>', caption: 'Three', alt_text: 'Three', change_summary: 'Fixes all checks.' },
  ]
  const evaluations = [
    evaluation('asset-one', review({ finding: 'Fix the champion-only issue.' })),
    evaluation('asset-two', review({ scientific: ['fail', 'pass'], failedDesign: ['visual_hierarchy'], finding: 'Fix the rejected-only issue.' })),
    evaluation('asset-three', review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] })),
  ]
  const sources = new Map()
  const workerPrompts = []
  const workerSchemas = []
  const workerBaselines = []
  const workerThreads = []
  const disposed = []
  let candidateIndex = 0
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 1,
    maxAttempts: 5,
    stagnationLimit: 2,
    startWorker: async () => {
      const threadId = `worker-${workerThreads.length + 1}`
      workerThreads.push(threadId)
      return threadId
    },
    runWorker: async ({ prompt, outputSchema, baseline }) => {
      workerPrompts.push(prompt)
      workerSchemas.push(outputSchema)
      workerBaselines.push(baseline?.asset_id ?? null)
      return candidates[candidateIndex]
    },
    disposeWorker: async threadId => disposed.push(threadId),
    processCandidate: async ({ candidate }) => {
      const current = evaluations[candidateIndex]
      sources.set(current.asset_id, candidate.svg)
      candidateIndex += 1
      return current
    },
    readRegisteredAsset: async (_workspace, assetId) => ({
      entry: { id: assetId, caption: assetId, alt_text: assetId, path: `assets/svg/${assetId}.svg`, visual_plan_id: 'mechanism' },
      bytes: Buffer.from(sources.get(assetId)),
      sha256: assetId.padEnd(64, 'a').slice(0, 64),
    }),
  })

  const delegated = await manager.delegate('mechanism')
  const completed = await waitForTerminal(manager, delegated.job.id)
  await manager.stop()

  assert.equal(completed.status, 'passed')
  assert.equal(completed.attempts, 3)
  assert.equal(completed.best.asset_id, 'asset-three')
  assert.equal(workerThreads.length, 3)
  assert.equal(new Set(workerThreads).size, 3)
  assert.deepEqual(disposed, workerThreads)
  assert.match(workerPrompts[1], /Champion baseline asset asset-one/)
  assert.match(workerPrompts[2], /Champion baseline asset asset-one/)
  assert.doesNotMatch(workerPrompts[2], /Champion baseline asset asset-two/)
  assert.match(workerPrompts[2], /champion-only issue/i)
  assert.doesNotMatch(workerPrompts[2], /rejected-only issue/i)
  assert.equal(workerSchemas[0], SVG_WORKER_OUTPUT_SCHEMA)
  assert.equal(workerSchemas[1], SVG_WORKER_REVISION_OUTPUT_SCHEMA)
  assert.equal(workerSchemas[2], SVG_WORKER_REVISION_OUTPUT_SCHEMA)
  assert.deepEqual(workerBaselines, [null, 'asset-one', 'asset-one'])
  assert.match(workerPrompts[1], /through svg_edit calls against stable element ids/i)
  assert.match(workerPrompts[1], /without SVG source/i)
  assert.deepEqual(completed.locked_constraints.scientific_checks, [
    'Input connects to Output.',
    'Every arrow points toward Output.',
  ])
  const regressions = lockRegressions({ scientific_checks: ['Input connects to Output.'] }, evaluations[1])
  assert.deepEqual(regressions, ['scientific check regressed: Input connects to Output.'])
})

test('duplicate challengers consume a bounded attempt and stop instead of looping forever', async t => {
  const workspace = await workspaceFixture(t)
  const candidate = { svg: '<svg>same</svg>', caption: 'Same', alt_text: 'Same', change_summary: 'No change.' }
  const sources = new Map()
  let processCalls = 0
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 1,
    maxAttempts: 2,
    stagnationLimit: 1,
    startWorker: async () => `worker-${processCalls + 1}`,
    runWorker: async () => candidate,
    processCandidate: async () => {
      processCalls += 1
      sources.set('asset-one', candidate.svg)
      return evaluation('asset-one', null, ['text_overlap'])
    },
    readRegisteredAsset: async () => ({
      entry: { id: 'asset-one', caption: 'Same', alt_text: 'Same', path: 'assets/svg/asset-one.svg', visual_plan_id: 'mechanism' },
      bytes: Buffer.from(sources.get('asset-one')),
      sha256: 'a'.repeat(64),
    }),
  })

  const delegated = await manager.delegate('mechanism')
  const completed = await waitForTerminal(manager, delegated.job.id)
  await manager.stop()

  assert.equal(completed.status, 'failed')
  assert.equal(completed.attempts, 2)
  assert.equal(processCalls, 1)
  assert.match(completed.last_feedback.join(' '), /bounded 2-attempt budget/i)
})

test('delegation returns while candidate processing continues in the background', async t => {
  const workspace = await workspaceFixture(t)
  let releaseProcessing
  let announceProcessing
  const processingStarted = new Promise(resolve => { announceProcessing = resolve })
  const processingGate = new Promise(resolve => { releaseProcessing = resolve })
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 1,
    maxAttempts: 1,
    startWorker: async () => 'async-worker-1',
    runWorker: async () => ({
      svg: '<svg>async-candidate</svg>',
      caption: 'Async',
      alt_text: 'Async',
      change_summary: 'Initial candidate.',
    }),
    processCandidate: async () => {
      announceProcessing()
      await processingGate
      return evaluation('asset-async', review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] }))
    },
  })

  const delegated = await manager.delegate('mechanism')
  let independentRootWork = false
  independentRootWork = true
  await processingStarted
  assert.equal(independentRootWork, true)
  assert.match(manager.status(delegated.job.id).job.status, /running|revising/)
  releaseProcessing()
  const completed = await waitForTerminal(manager, delegated.job.id)
  await manager.stop()
  assert.equal(completed.status, 'passed')
})

test('a configured six-worker pool starts six independent SVG jobs concurrently', async t => {
  const workspace = await workspaceFixture(t, 6)
  let started = 0
  let releaseWorkers
  let announceAllStarted
  const workerGate = new Promise(resolve => { releaseWorkers = resolve })
  const allStarted = new Promise(resolve => { announceAllStarted = resolve })
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 6,
    maxAttempts: 1,
    startWorker: async ({ job }) => `parallel-worker-${job.visual_plan_id}`,
    runWorker: async ({ job }) => {
      started += 1
      if (started === 6) announceAllStarted()
      await workerGate
      return {
        svg: `<svg>${job.visual_plan_id}</svg>`,
        caption: job.visual_plan_id,
        alt_text: job.visual_plan_id,
        change_summary: 'Independent parallel candidate.',
      }
    },
    processCandidate: async ({ job }) => evaluation(
      `asset-${job.visual_plan_id}`,
      review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] }),
    ),
  })

  const delegated = await Promise.all([
    'mechanism',
    'mechanism-2',
    'mechanism-3',
    'mechanism-4',
    'mechanism-5',
    'mechanism-6',
  ].map(planId => manager.delegate(planId)))

  try {
    await Promise.race([
      allStarted,
      new Promise((_, reject) => setTimeout(() => reject(new Error('six SVG workers did not start concurrently')), 1_000)),
    ])
    assert.equal(started, 6)
    assert.equal(manager.status().jobs.filter(job => /running|revising/.test(job.status)).length, 6)
  } finally {
    releaseWorkers()
  }

  const completed = await Promise.all(delegated.map(item => waitForTerminal(manager, item.job.id)))
  await manager.stop()
  assert.deepEqual(completed.map(job => job.status), Array(6).fill('passed'))
})

test('a fresh job resumes from the retained champion instead of regenerating from scratch', async t => {
  const workspace = await workspaceFixture(t)
  const sources = new Map()
  const baselines = []
  const prompts = []
  let candidateIndex = 0
  const candidates = [
    { svg: '<svg>retained-one</svg>', caption: 'One', alt_text: 'One', change_summary: 'Initial.' },
    { svg: '<svg>retained-two</svg>', caption: 'Two', alt_text: 'Two', change_summary: 'Edited.' },
  ]
  const manager = new SvgJobManager({
    workspace,
    maxConcurrent: 1,
    maxAttempts: 1,
    maxJobsPerPlan: 2,
    startWorker: async () => `resume-worker-${candidateIndex + 1}`,
    runWorker: async ({ baseline, outputSchema, prompt }) => {
      baselines.push({ asset: baseline?.asset_id ?? null, outputSchema })
      prompts.push(prompt)
      return candidates[candidateIndex]
    },
    processCandidate: async ({ candidate }) => {
      const index = candidateIndex
      candidateIndex += 1
      const assetId = `retained-asset-${index + 1}`
      sources.set(assetId, candidate.svg)
      return index === 0
        ? evaluation(assetId, review())
        : evaluation(assetId, review({ verdict: 'pass', scientific: ['pass', 'pass'], failedDesign: [] }))
    },
    readRegisteredAsset: async (_workspace, assetId) => ({
      entry: { id: assetId, caption: assetId, alt_text: assetId, path: `assets/svg/${assetId}.svg`, visual_plan_id: 'mechanism' },
      bytes: Buffer.from(sources.get(assetId)),
      sha256: assetId.padEnd(64, 'a').slice(0, 64),
    }),
  })

  const first = await manager.delegate('mechanism')
  assert.equal((await waitForTerminal(manager, first.job.id)).status, 'failed')
  const second = await manager.delegate('mechanism')
  assert.equal((await waitForTerminal(manager, second.job.id)).status, 'passed')
  await manager.stop()

  assert.equal(baselines[0].asset, null)
  assert.equal(baselines[0].outputSchema, SVG_WORKER_OUTPUT_SCHEMA)
  assert.equal(baselines[1].asset, 'retained-asset-1')
  assert.equal(baselines[1].outputSchema, SVG_WORKER_REVISION_OUTPUT_SCHEMA)
  assert.match(prompts[1], /Correct the remaining directed connection/i)
  assert.doesNotMatch(prompts[1], /exhausted its bounded/i)
  await assert.rejects(manager.delegate('mechanism'), /exhausted its bounded 2-job generation budget/i)
})
