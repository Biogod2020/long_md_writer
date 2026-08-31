import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { chmod, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  buildAppServerArgs,
  dynamicToolResponse,
  loadHostConfig,
  LongWriterHost,
  nextPublicationPrompt,
  svgWorkerThreadPermissions,
  svgWorkerTurnPermissions,
} from '../app-server/host.js'
import { WRITER_POLICY, REVIEWER_POLICY, SVG_WORKER_POLICY, VISUAL_REVIEWER_POLICY, projectPublicationGoal } from '../app-server/policy.js'
import { PublicationToolRuntime } from '../app-server/publication-tools.js'
import { RunRecorder } from '../app-server/run-recorder.js'
import { SearchToolRuntime } from '../app-server/search-tools.js'
import { DESIGN_CHECK_KEYS } from '../svg/design.js'
import {
  appendVisualPreflight,
  initializeProject,
  publicationStatus,
  readAssetManifest,
  registerAsset,
  setVisualContract,
} from '../lib/project-store.js'

function project() {
  return {
    title: 'App Server publication',
    objective: 'Verify one controlled publication host',
    audience: 'medical students',
    language: 'English',
    sections: [
      { id: 'intro', title: 'Introduction', objective: 'Frame the topic', target_words: 8 },
      { id: 'method', title: 'Method', objective: 'Explain the mechanism', target_words: 8 },
    ],
    visual_contract: {
      schema_version: 1,
      figure_start: 1,
      minimum_figures: 0,
      required_sections: [],
      figures: [],
    },
    quality_contract: {
      minimum_section_ratio: 0.75,
      maximum_section_ratio: 4,
      minimum_total_ratio: 0.75,
      maximum_total_ratio: 4,
      long_sentence_chars: 80,
      maximum_long_sentence_ratio: 1,
      minimum_review_score: 85,
    },
    research_contract: { minimum_image_searches: 0, minimum_image_candidates: 0 },
  }
}

async function fixture(t, overrides = {}) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-app-server-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  const goals = []
  const runtime = new PublicationToolRuntime({
    workspace,
    setGoal: async (objective, status) => {
      const goal = { objective, status }
      goals.push(goal)
      return goal
    },
    completeGoal: async () => ({ status: 'complete' }),
    requestReview: overrides.requestReview ?? (async () => { throw new Error('review is outside this fixture') }),
    inspectVisual: overrides.inspectVisual,
    delegateSvg: overrides.delegateSvg,
    svgStatus: overrides.svgStatus,
  })
  return { workspace, runtime, goals }
}

test('App Server arguments declare a Responses provider without embedding credentials', () => {
  const args = buildAppServerArgs({
    model_provider: 'iworld',
    provider: {
      name: 'iWorld Muse',
      base_url: 'https://example.test/v1',
      env_key: 'IWORLD_API_KEY',
      wire_api: 'responses',
    },
    mcp_servers: {
      web: { command_env: 'SEARCH_BIN', required: true },
    },
  }, { SEARCH_BIN: '/opt/read-only-search' })
  assert.ok(args.includes('model_providers.iworld.wire_api="responses"'))
  assert.ok(args.includes('model_providers.iworld.env_key="IWORLD_API_KEY"'))
  assert.ok(args.includes('mcp_servers.web.command="/opt/read-only-search"'))
  assert.equal(args.some(value => value.includes('actual-secret')), false)
})

test('host config permits a bounded six-worker SVG pool and rejects seven', async t => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'longwriter-host-config-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const configPath = path.join(directory, 'config.json')
  const config = {
    schema_version: 1,
    model: 'muse-spark-1.2',
    model_provider: 'iworld',
    svg_workers: { max_concurrent: 6, max_preflights_per_attempt: 3, shell_steer_after_commands: 12 },
  }
  await writeFile(configPath, `${JSON.stringify(config)}\n`)
  const loaded = await loadHostConfig(configPath)
  assert.equal(loaded.svg_workers.max_concurrent, 6)
  assert.equal(loaded.svg_workers.max_preflights_per_attempt, 3)
  assert.equal(loaded.svg_workers.shell_steer_after_commands, 12)
  config.svg_workers.max_concurrent = 7
  await writeFile(configPath, `${JSON.stringify(config)}\n`)
  await assert.rejects(loadHostConfig(configPath), /max_concurrent must be an integer in 1\.\.6/)
})

test('SVG workers get scratch-only writes, networked shell turns, and Approve for me review', async t => {
  const scratch = await mkdtemp(path.join(os.tmpdir(), 'longwriter-svg-worker-scratch-'))
  t.after(() => rm(scratch, { recursive: true, force: true }))
  assert.deepEqual(svgWorkerThreadPermissions(scratch), {
    cwd: scratch,
    runtimeWorkspaceRoots: [scratch],
    approvalPolicy: 'on-request',
    approvalsReviewer: 'auto_review',
    sandbox: 'workspace-write',
  })
  assert.deepEqual(svgWorkerTurnPermissions(scratch), {
    cwd: scratch,
    runtimeWorkspaceRoots: [scratch],
    approvalPolicy: 'on-request',
    approvalsReviewer: 'auto_review',
    sandboxPolicy: {
      type: 'workspaceWrite',
      writableRoots: [scratch],
      networkAccess: true,
      excludeSlashTmp: true,
      excludeTmpdirEnvVar: true,
    },
  })
})

test('the dynamic contract exposes only bounded publication tools', async t => {
  const { runtime } = await fixture(t)
  const specs = runtime.specs()
  assert.deepEqual(specs.map(tool => tool.name).sort(), [
    'commit_chunk',
    'finalize_publication',
    'image_submit',
    'initialize_publication',
    'inspect_visual',
    'mermaid_submit',
    'plan_visuals',
    'publication_status',
    'review_publication',
    'revise_chunk',
    'svg_check',
    'svg_collect',
    'svg_delegate',
    'svg_preflight',
    'svg_status',
    'svg_submit',
    'svg_wait',
  ])
  assert.ok(specs.every(tool => tool.type === 'function' && tool.inputSchema.type === 'object'))
  assert.deepEqual(specs.find(tool => tool.name === 'inspect_visual').inputSchema.required, ['asset_id', 'preflight_id'])
  assert.ok(specs.find(tool => tool.name === 'initialize_publication').inputSchema.properties.project.required.includes('research_contract'))
})

test('initialization creates canonical records and installs a measurable project goal', async t => {
  const { workspace, runtime, goals } = await fixture(t)
  const result = await runtime.execute('initialize_publication', { project: project() }, {
    threadId: 'thread-1',
    turnId: 'turn-1',
  })
  assert.equal(result.created, true)
  assert.equal(goals.length, 1)
  assert.equal(goals[0].status, 'active')
  assert.equal(goals[0].objective, projectPublicationGoal(project()))
  assert.match(goals[0].objective, /deterministic validation/i)
  assert.equal((await publicationStatus(workspace)).chunks, 0)
})

test('initialization cannot smuggle a completed visual plan past the research phase', async t => {
  const { runtime } = await fixture(t)
  const invalid = project()
  invalid.visual_contract.figures = [{
    id: 'premature',
    number: 1,
    section_id: 'intro',
    kind: 'svg',
    purpose: 'This must be planned only after research.',
    required_labels: [],
  }]
  await assert.rejects(
    runtime.execute('initialize_publication', { project: invalid }, { threadId: 'thread-1', turnId: 'turn-init' }),
    /figures must be empty until research completes/,
  )
})

test('one terminal publication action is allowed per turn', async t => {
  const { runtime } = await fixture(t)
  await runtime.execute('initialize_publication', { project: project() }, {
    threadId: 'thread-1',
    turnId: 'turn-init',
  })
  await runtime.execute('commit_chunk', {
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'A controlled first chunk explains the publication topic with sufficient detail.',
  }, { threadId: 'thread-1', turnId: 'turn-write' })
  await assert.rejects(
    runtime.execute('commit_chunk', {
      section_id: 'method',
      chunk_id: 'method-01',
      markdown: 'A forbidden second chunk in the same turn must not reach the store.',
    }, { threadId: 'thread-1', turnId: 'turn-write' }),
    /already completed its publication unit/,
  )
})

test('successful SVG delegation is a host-enforced terminal turn unit', async t => {
  const { runtime } = await fixture(t, {
    delegateSvg: async visualPlanId => ({ id: 'job-one', visual_plan_id: visualPlanId, status: 'queued' }),
  })
  const result = await runtime.execute('svg_delegate', { visual_plan_id: 'fig-one' }, {
    threadId: 'thread-1',
    turnId: 'turn-delegate',
  })
  assert.equal(result.turn_complete, true)
  assert.equal(runtime.terminalToolForTurn('turn-delegate'), 'svg_delegate')
  await assert.rejects(
    runtime.execute('commit_chunk', {
      section_id: 'intro',
      chunk_id: 'intro-after-delegate',
      markdown: 'This mutation must be deferred to a fresh root turn.',
    }, { threadId: 'thread-1', turnId: 'turn-delegate' }),
    /already completed its publication unit through svg_delegate/,
  )
})

test('root svg_submit cannot fork a delegated visual revision chain', async t => {
  const { runtime } = await fixture(t, {
    svgStatus: () => ({
      jobs: [{ id: 'svg-job-one', visual_plan_id: 'fig-one', status: 'passed' }],
    }),
  })
  await assert.rejects(
    runtime.execute('svg_submit', {
      visual_plan_id: 'fig-one',
      svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><text x="10" y="30">replacement</text></svg>',
      dry_run: true,
    }, { threadId: 'thread-1', turnId: 'turn-direct-svg' }),
    /unavailable for delegated visual plan fig-one/,
  )
})

test('review_publication stops before independent visual review when deterministic validation fails', async t => {
  let reviewCalls = 0
  const { runtime } = await fixture(t, {
    requestReview: async () => {
      reviewCalls += 1
      throw new Error('deterministically invalid work must not reach review')
    },
  })
  await runtime.execute('initialize_publication', { project: project() }, {
    threadId: 'thread-1',
    turnId: 'turn-init',
  })
  const result = await runtime.execute('review_publication', {}, {
    threadId: 'thread-1',
    turnId: 'turn-review',
  })

  assert.equal(result.reviewed, false)
  assert.equal(result.reason, 'deterministic-validation-failed')
  assert.equal(result.validator.passed, false)
  assert.equal(reviewCalls, 0)
})

test('provider-encoded JSON string arguments are normalized only for declared JSON fields', async t => {
  const { runtime } = await fixture(t)
  await runtime.execute('initialize_publication', { project: project() }, {
    threadId: 'thread-1',
    turnId: 'turn-init',
  })
  const result = await runtime.execute('plan_visuals', {
    visual_contract: JSON.stringify({
      schema_version: 1,
      figures: [{
        id: 'lead-axis',
        section_id: 'intro',
        kind: 'svg',
        purpose: 'Explain lead-axis projection.',
        required_labels: ['Lead axis'],
        review_required: true,
      }],
    }),
  }, { threadId: 'thread-1', turnId: 'turn-plan' })
  assert.equal(result.planned, true)
  assert.equal(result.visual_contract.figures[0].id, 'lead-axis')
})

test('writer policy makes full-manuscript reading and finalize-only completion explicit', () => {
  assert.match(WRITER_POLICY, /read the complete current article\.md from beginning to end/i)
  assert.match(WRITER_POLICY, /Only finalize_publication may complete the goal/i)
  assert.match(WRITER_POLICY, /sandbox is read-only/i)
  assert.match(WRITER_POLICY, /inspect_visual/)
  assert.match(WRITER_POLICY, /ephemeral reviewer thread/i)
  assert.match(WRITER_POLICY, /svg_delegate/)
  assert.match(WRITER_POLICY, /Do not redraw a delegated visual/i)
  assert.match(SVG_WORKER_POLICY, /use the internet/i)
  assert.match(SVG_WORKER_POLICY, /run shell commands/i)
  assert.match(SVG_WORKER_POLICY, /current scratch workspace/i)
  assert.match(SVG_WORKER_POLICY, /root writer's read-only profile does not apply/i)
  assert.match(SVG_WORKER_POLICY, /modify that exact SVG like code through svg_edit/i)
  assert.match(SVG_WORKER_POLICY, /svg_preflight_draft/i)
  assert.match(SVG_WORKER_POLICY, /Batch coordinated local operations atomically/i)
  assert.doesNotMatch(SVG_WORKER_POLICY, /Never call shell/i)
})

test('writer policy emphasizes autonomy and omits copyright sermons', () => {
  assert.match(WRITER_POLICY, /You own the teaching/)
  assert.match(WRITER_POLICY, /reader-friendly/)
  assert.match(WRITER_POLICY, /读者容易读懂/)
  assert.match(WRITER_POLICY, /scientifically reasonable/)
  assert.match(WRITER_POLICY, /图文并茂/)
  assert.match(WRITER_POLICY, /符合用户意图/)
  assert.match(WRITER_POLICY, /准确/)
  assert.match(WRITER_POLICY, /If the brief already states a measurable contract/)
  assert.match(WRITER_POLICY, /skip request_user_input/)
  assert.match(WRITER_POLICY, /image_submit/)
  assert.match(WRITER_POLICY, /精炼/)
  assert.match(WRITER_POLICY, /floor, not the target/)
  assert.match(WRITER_POLICY, /Call them while you work/)
  assert.doesNotMatch(WRITER_POLICY, /retained candidates/)
  assert.doesNotMatch(WRITER_POLICY, /clinical/)
  assert.doesNotMatch(WRITER_POLICY, /anatomical/)
  assert.doesNotMatch(WRITER_POLICY, /not permission to copy/)
  assert.doesNotMatch(WRITER_POLICY, /implicitly licensed/)
  assert.doesNotMatch(WRITER_POLICY, /copyright/)
})

test('reviewer policy judges the same four teaching outcomes', () => {
  assert.match(REVIEWER_POLICY, /读者容易读懂/)
  assert.match(REVIEWER_POLICY, /图文并茂/)
  assert.match(REVIEWER_POLICY, /符合用户意图/)
  assert.match(REVIEWER_POLICY, /准确/)
  assert.match(REVIEWER_POLICY, /scientifically reasonable/)
  assert.doesNotMatch(REVIEWER_POLICY, /copyright/)
  assert.match(REVIEWER_POLICY, /Do not open image files/i)
  assert.match(VISUAL_REVIEWER_POLICY, /exactly the one attached retained PNG/i)
  assert.match(VISUAL_REVIEWER_POLICY, /For photographs, each required label names a subject or detail/i)
})

test('inspect_visual returns metadata only and root tool responses reject inline images', async t => {
  const visualResult = {
    status: 'inspected_pass',
    cached: false,
    receipt: { preview_sha256: 'a'.repeat(64), verdict: 'pass' },
  }
  const { runtime } = await fixture(t, { inspectVisual: async () => visualResult })
  const result = await runtime.execute('inspect_visual', { asset_id: 'asset-one', preflight_id: 'preflight-one' }, {
    threadId: 'thread-1',
    turnId: 'turn-image',
  })
  assert.deepEqual(result, visualResult)
  const response = dynamicToolResponse(result)
  assert.deepEqual(response.contentItems.map(item => item.type), ['inputText'])
  assert.throws(
    () => dynamicToolResponse({ image: { data_url: 'data:image/png;base64,AAAA' } }),
    /inline image tool results are forbidden/,
  )
})

test('next-unit prompting derives unfinished prose and research-gated visual work from canonical state', () => {
  const publication = {
    ...project(),
    quality_contract: {
      minimum_section_ratio: 0.75,
      maximum_section_ratio: 1.25,
      minimum_total_ratio: 0.75,
      maximum_total_ratio: 1.2,
      long_sentence_chars: 80,
      maximum_long_sentence_ratio: 0.2,
      minimum_review_score: 85,
      require_zero_placeholders: true,
      require_review: true,
    },
    visual_contract: {
      schema_version: 1,
      figure_start: 1,
      minimum_figures: 1,
      required_sections: ['intro'],
      figures: [],
    },
  }
  const common = {
    config: { research_gate: { minimum_successful_calls: 3, required_tools: ['longwriter_search', 'longwriter_open'] } },
    project: publication,
    manifest: { assets: [], visual_preflights: [], visual_reviews: [] },
    article: '# Draft',
    runState: {},
  }
  const researchPrompt = nextPublicationPrompt({
    ...common,
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 0, target_words: 8, completion_ratio: 0 }] },
  })
  assert.match(researchPrompt, /3 more successful research calls/i)
  assert.match(researchPrompt, /plan_visuals/)
  assert.match(researchPrompt, /读者容易读懂/)
  assert.match(researchPrompt, /图文并茂/)
  assert.match(researchPrompt, /floor, not the target/)
  const prosePrompt = nextPublicationPrompt({
    ...common,
    project: {
      ...publication,
      visual_contract: {
        ...publication.visual_contract,
        figures: [{
          id: 'intro-figure', number: 1, section_id: 'intro', kind: 'svg', purpose: 'Explain.', required_labels: [], review_required: true,
        }],
      },
    },
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 0, target_words: 8, completion_ratio: 0, chunk_ids: [], long_sentence_ratio: 0 }] },
  })
  assert.match(prosePrompt, /next required unit is section intro/i)
  assert.match(prosePrompt, /intro-figure/)
  assert.match(prosePrompt, /fill the bounded SVG worker pool before prose/i)
  assert.match(prosePrompt, /only unit for this turn/i)
  const saturatedPoolPrompt = nextPublicationPrompt({
    ...common,
    config: { ...common.config, svg_workers: { max_concurrent: 2 } },
    project: {
      ...publication,
      visual_contract: {
        ...publication.visual_contract,
        figures: ['one', 'two', 'three'].map((id, index) => ({
          id: `intro-${id}`,
          number: index + 1,
          section_id: 'intro',
          kind: 'svg',
          purpose: `Explain ${id}.`,
          required_labels: [],
          review_required: true,
        })),
      },
    },
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 0, target_words: 8, completion_ratio: 0, chunk_ids: [], long_sentence_ratio: 0 }] },
    runState: {
      svg_jobs: {
        'job-one': { visual_plan_id: 'intro-one', status: 'running', created_at: '2026-01-01T00:00:00Z' },
        'job-two': { visual_plan_id: 'intro-two', status: 'running', created_at: '2026-01-01T00:00:01Z' },
      },
    },
  })
  assert.match(saturatedPoolPrompt, /currently 0\/8 words/i)
  assert.doesNotMatch(saturatedPoolPrompt, /svg_delegate/i)
  const exhaustedPeerPrompt = nextPublicationPrompt({
    ...common,
    config: { ...common.config, svg_workers: { max_concurrent: 2 } },
    project: {
      ...publication,
      visual_contract: {
        ...publication.visual_contract,
        figures: ['failed', 'active'].map((id, index) => ({
          id: `intro-${id}`,
          number: index + 1,
          section_id: 'intro',
          kind: 'svg',
          purpose: `Explain ${id}.`,
          required_labels: [],
          review_required: true,
        })),
      },
    },
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 0, target_words: 8, completion_ratio: 0, chunk_ids: [], long_sentence_ratio: 0 }] },
    runState: {
      svg_jobs: {
        'job-failed': {
          id: 'job-failed', visual_plan_id: 'intro-failed', status: 'failed', generation: 1, maximum_generations: 1,
          created_at: '2026-01-01T00:00:00Z',
        },
        'job-active': {
          id: 'job-active', visual_plan_id: 'intro-active', status: 'running', generation: 1, maximum_generations: 1,
          created_at: '2026-01-01T00:00:01Z',
        },
      },
    },
  })
  assert.match(exhaustedPeerPrompt, /svg_wait for job-active/i)
  assert.match(exhaustedPeerPrompt, /until every already-delegated SVG job is terminal/i)
  assert.doesNotMatch(exhaustedPeerPrompt, /svg_delegate/i)
  const sha = 'a'.repeat(64)
  const tighteningPrompt = nextPublicationPrompt({
    ...common,
    project: {
      ...publication,
      visual_contract: {
        ...publication.visual_contract,
        figures: [{
          id: 'intro-figure', number: 1, section_id: 'intro', kind: 'svg', purpose: 'Explain.', required_labels: [], review_required: true,
        }],
      },
    },
    manifest: {
      assets: [{ id: 'intro-svg', path: 'assets/svg/intro.svg', visual_plan_id: 'intro-figure', sha256: sha }],
      visual_preflights: [{
        id: 'pf-1', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
        passed: true, preview_asset_id: 'intro-preview',
      }],
      visual_reviews: [{
        id: 'rv-1', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
        preflight_id: 'pf-1', verdict: 'pass',
      }],
    },
    article: '![axis](assets/svg/intro.svg)',
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 12, target_words: 8, completion_ratio: 1.5, chunk_ids: ['intro-01'], long_sentence_ratio: 0.4 }] },
  })
  assert.match(tighteningPrompt, /violates the initialized quality ceiling/i)
  assert.match(tighteningPrompt, /revise_chunk/i)

  const totalTighteningPrompt = nextPublicationPrompt({
    ...common,
    project: {
      ...publication,
      quality_contract: {
        ...publication.quality_contract,
        maximum_section_ratio: 1.3,
        maximum_total_ratio: 1.1,
      },
      visual_contract: {
        ...publication.visual_contract,
        figures: [{
          id: 'intro-figure', number: 1, section_id: 'intro', kind: 'svg', purpose: 'Explain.', required_labels: [], review_required: true,
        }],
      },
    },
    manifest: {
      assets: [{ id: 'intro-svg', path: 'assets/svg/intro.svg', visual_plan_id: 'intro-figure', sha256: sha }],
      visual_preflights: [{
        id: 'pf-total', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
        passed: true, preview_asset_id: 'intro-preview',
      }],
      visual_reviews: [{
        id: 'rv-total', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
        preflight_id: 'pf-total', verdict: 'pass',
      }],
    },
    article: '![axis](assets/svg/intro.svg)',
    status: {
      total_words: 20,
      target_words: 16,
      completion_ratio: 1.25,
      sections: [
        { id: 'intro', title: 'Introduction', word_count: 10, target_words: 8, completion_ratio: 1.25, chunk_ids: ['intro-01'], long_sentence_ratio: 0 },
        { id: 'method', title: 'Method', word_count: 10, target_words: 8, completion_ratio: 1.25, chunk_ids: ['method-01'], long_sentence_ratio: 0 },
      ],
    },
  })
  assert.match(totalTighteningPrompt, /complete article violates the initialized total-length ceiling/i)
  assert.match(totalTighteningPrompt, /remove at least 3 words overall/i)
  assert.match(totalTighteningPrompt, /chunk intro-01/i)
  assert.match(totalTighteningPrompt, /do not call review_publication/i)

  const failedReviewPrompt = nextPublicationPrompt({
    ...common,
    project: {
      ...publication,
      visual_contract: {
        ...publication.visual_contract,
        figures: [{
          id: 'intro-photo', number: 1, section_id: 'intro', kind: 'photo', purpose: 'Show the device.', required_labels: ['Device'], review_required: true,
        }],
      },
    },
    manifest: {
      assets: [{ id: 'intro-photo-asset', path: 'assets/photos/device.png', visual_plan_id: 'intro-photo', sha256: sha }],
      visual_preflights: [{
        id: 'pf-photo', asset_id: 'intro-photo-asset', asset_sha256: sha, visual_plan_id: 'intro-photo',
        passed: true, preview_asset_id: 'intro-photo-preview',
      }],
      visual_reviews: [{
        id: 'rv-photo-fail', asset_id: 'intro-photo-asset', asset_sha256: sha, visual_plan_id: 'intro-photo',
        preflight_id: 'pf-photo', verdict: 'fail', summary: 'The device is obscured.', findings: ['Required subject is unclear.'],
      }],
    },
    article: '# Draft',
    status: { sections: [{ id: 'intro', title: 'Introduction', word_count: 0, target_words: 8, completion_ratio: 0, chunk_ids: [], long_sentence_ratio: 0 }] },
  })
  assert.match(failedReviewPrompt, /Do not inspect the unchanged asset again/i)
  assert.match(failedReviewPrompt, /supersedes_asset_id=intro-photo-asset/)
  assert.match(failedReviewPrompt, /longwriter_search_images/)

  const reviewedProject = {
    ...publication,
    visual_contract: {
      ...publication.visual_contract,
      figures: [{
        id: 'intro-figure', number: 1, section_id: 'intro', kind: 'svg', purpose: 'Explain.', required_labels: [], review_required: true,
      }],
    },
  }
  const reviewedManifest = {
    assets: [{ id: 'intro-svg', path: 'assets/svg/intro.svg', visual_plan_id: 'intro-figure', sha256: sha }],
    visual_preflights: [{
      id: 'pf-1', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
      passed: true, preview_asset_id: 'intro-preview',
    }],
    visual_reviews: [{
      id: 'rv-1', asset_id: 'intro-svg', asset_sha256: sha, visual_plan_id: 'intro-figure',
      preflight_id: 'pf-1', verdict: 'pass',
    }],
  }
  const reviewedStatus = {
    article_sha256: sha,
    sections: [
      { id: 'intro', title: 'Introduction', word_count: 8, target_words: 8, completion_ratio: 1, chunk_ids: ['intro-01'], long_sentence_ratio: 0 },
      { id: 'method', title: 'Method', word_count: 8, target_words: 8, completion_ratio: 1, chunk_ids: ['method-01'], long_sentence_ratio: 0 },
    ],
  }
  const passedReviewPrompt = nextPublicationPrompt({
    ...common,
    project: reviewedProject,
    manifest: reviewedManifest,
    article: '![axis](assets/svg/intro.svg)',
    status: reviewedStatus,
    runState: {
      last_publication_review: {
        article_sha256: sha,
        visual_audit_passed: true,
        verdict: 'pass',
        overall_score: 96,
        critical_issue_count: 0,
      },
    },
  })
  assert.match(passedReviewPrompt, /Call finalize_publication now/i)
  assert.doesNotMatch(passedReviewPrompt, /Run review_publication now/i)

  const staleReviewPrompt = nextPublicationPrompt({
    ...common,
    project: reviewedProject,
    manifest: reviewedManifest,
    article: '![axis](assets/svg/intro.svg)',
    status: reviewedStatus,
    runState: {
      last_publication_review: {
        article_sha256: 'b'.repeat(64),
        visual_audit_passed: true,
        verdict: 'pass',
        overall_score: 96,
        critical_issue_count: 0,
      },
    },
  })
  assert.match(staleReviewPrompt, /Run review_publication now/i)
})

test('search bridge exposes flat provider-compatible functions and executes a bounded runner', async t => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-search-bridge-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  const command = path.join(workspace, 'echo-json')
  await writeFile(command, '#!/bin/sh\ncat\n')
  await chmod(command, 0o755)
  const runtime = new SearchToolRuntime({
    command,
    project: path.join(workspace, 'search-project'),
    runner: path.join(workspace, 'search-tool.py'),
    timeoutMs: 5000,
  })
  assert.deepEqual(runtime.specs().map(tool => tool.name), [
    'longwriter_search',
    'longwriter_search_images',
    'longwriter_open',
    'longwriter_find',
  ])
  assert.ok(runtime.specs().every(tool => tool.type === 'function'))
  assert.deepEqual(await runtime.execute('longwriter_search', { query: 'ECG electrodes' }), { query: 'ECG electrodes' })
})

async function visualFixture(t, count = 1, kind = 'svg', options = {}) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-visual-review-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  const publication = project()
  publication.visual_contract.minimum_figures = count
  publication.visual_contract.required_sections = ['intro']
  await initializeProject(workspace, publication)
  await setVisualContract(workspace, {
    schema_version: 1,
    figure_start: 1,
    minimum_figures: count,
    required_sections: ['intro'],
    figures: Array.from({ length: count }, (_, index) => ({
      id: `visual-${index + 1}`,
      number: index + 1,
      section_id: 'intro',
      kind,
      purpose: `Explain visual concept ${index + 1}.`,
      required_labels: [`Label ${index + 1}`],
      review_required: true,
    })),
  })
  const items = []
  for (let index = 0; index < count; index += 1) {
    const number = index + 1
    const assetId = `visual-asset-${number}`
    const previewId = `visual-preview-${number}`
    const source = await registerAsset(workspace, {
      id: assetId,
      source: 'test',
      path: kind === 'photo' ? `assets/photos/${assetId}.png` : `assets/svg/${assetId}.svg`,
      caption: `Visual ${number}`,
      alt_text: `Visual ${number} alt text.`,
      provenance: 'generated:test',
      licence: 'generated_internal',
      used_in: ['intro'],
      visual_plan_id: `visual-${number}`,
      bytes: kind === 'photo'
        ? Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, number])
        : Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg"><text>Label ${number}</text></svg>`),
    })
    const preview = await registerAsset(workspace, {
      id: previewId,
      source: 'tool',
      path: `assets/reviews/${previewId}.png`,
      caption: `Preview ${number}`,
      alt_text: `Preview ${number}.`,
      provenance: 'derived:test',
      licence: 'generated_internal',
      used_in: [],
      derivative_of: {
        asset_id: source.entry.id,
        asset_sha256: source.sha256,
        purpose: kind === 'photo' ? 'photo-preview' : 'svg-preview',
      },
      bytes: Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, number]),
    })
    const preflight = await appendVisualPreflight(workspace, {
      asset_id: source.entry.id,
      asset_sha256: source.sha256,
      visual_plan_id: `visual-${number}`,
      preview_asset_id: preview.entry.id,
      preview_sha256: preview.sha256,
      metric_mode: kind === 'photo' ? 'photo' : 'coretext',
      renderer: 'test-renderer',
      passed: options.preflightPassed ?? true,
      issues: options.preflightPassed === false ? ['text_overlap:0:"Label":1:"Other"'] : [],
      warnings: [],
    })
    items.push({ assetId, preflightId: preflight.id, previewId })
  }
  return { workspace, items }
}

class VisualReviewClient extends EventEmitter {
  constructor(options = {}) {
    super()
    this.handler = null
    this.starts = []
    this.inputs = []
    this.unsubscribes = []
    this.interrupts = []
    this.pendingTurns = new Map()
    this.mismatchField = options.mismatchField
    this.toolOnFirstAttempt = options.toolOnFirstAttempt === true
    this.emptyFailOnFirstAttempt = options.emptyFailOnFirstAttempt === true
  }

  setServerRequestHandler(handler) { this.handler = handler }
  async start() {}
  async initialize() { return { userAgent: 'Codex Desktop/0.151.0 (test)' } }
  async close() {}

  async request(method, params) {
    if (method === 'thread/start') {
      assert.ok(['longwriter-visual-reviewer', 'longwriter-visual-diagnostic'].includes(params.threadSource))
      assert.match(params.developerInstructions, /single-image classification turn/i)
      const id = `visual-review-thread-${this.starts.length + 1}`
      this.starts.push(params)
      return { thread: { id } }
    }
    if (method === 'turn/start') {
      this.inputs.push(params.input)
      assert.deepEqual(params.input.map(item => item.type), ['text', 'localImage'])
      assert.equal(params.collaborationMode.mode, 'default')
      assert.match(params.collaborationMode.settings.developer_instructions, /host rejects and interrupts any tool use/i)
      const binding = JSON.parse(params.input[0].text.match(/Exact binding: (\{[^\n]+\})/)?.[1] ?? '{}')
      const labels = JSON.parse(params.input[0].text.match(/Required (?:visible text labels|visibly confirmed subjects\/details): (\[[^\n]*\])/)?.[1] ?? '[]')
      const scientificCriteria = JSON.parse(params.input[0].text.match(/Exact scientific criteria: (\[[^\n]*\])/)?.[1] ?? '[]')
      const review = {
        ...binding,
        verdict: 'pass',
        summary: 'The single preview is readable and complete.',
        findings: [],
        checked_labels: labels,
        scientific_checks: scientificCriteria.map(criterion => ({
          criterion,
          verdict: 'pass',
          evidence: 'The planned relation is visibly encoded in the synthetic preview.',
        })),
        design_checks: Object.fromEntries(DESIGN_CHECK_KEYS.map(key => [key, 'pass'])),
      }
      if (this.mismatchField) review[this.mismatchField] = 'f'.repeat(64)
      if (this.emptyFailOnFirstAttempt && this.inputs.length === 1) {
        review.verdict = 'fail'
        review.summary = 'The layout fails, but this deliberately malformed response omits actionable findings.'
        review.findings = []
        review.design_checks.composition_spacing = 'fail'
      }
      const turn = {
        id: `visual-review-turn-${this.inputs.length}`,
        status: 'completed',
        items: [{ type: 'agentMessage', id: `visual-review-message-${this.inputs.length}`, text: JSON.stringify(review) }],
      }
      if (this.toolOnFirstAttempt && this.inputs.length === 1) {
        this.pendingTurns.set(turn.id, { ...turn, status: 'inProgress', items: [] })
        setImmediate(() => this.emit('notification', {
          method: 'item/started',
          params: {
            threadId: params.threadId,
            turnId: turn.id,
            item: { type: 'commandExecution', id: 'forbidden-review-command', status: 'inProgress' },
          },
        }))
        return { turn: { id: turn.id } }
      }
      this.emit('notification', { method: 'turn/completed', params: { threadId: params.threadId, turn } })
      return { turn: { id: turn.id } }
    }
    if (method === 'turn/interrupt') {
      this.interrupts.push(params)
      const pending = this.pendingTurns.get(params.turnId)
      assert.ok(pending)
      this.pendingTurns.delete(params.turnId)
      setImmediate(() => this.emit('notification', {
        method: 'turn/completed',
        params: { threadId: params.threadId, turn: { ...pending, status: 'interrupted' } },
      }))
      return {}
    }
    if (method === 'thread/unsubscribe') {
      this.unsubscribes.push(params.threadId)
      return { status: 'unsubscribed' }
    }
    throw new Error(`unexpected visual fake-client request: ${method}`)
  }
}

test('ephemeral visual reviewers receive one image each, persist hash-bound receipts, and reuse exact cached reviews', async t => {
  const { workspace, items } = await visualFixture(t, 11)
  const client = new VisualReviewClient()
  const host = new LongWriterHost({
    workspace,
    codexHome: path.join(workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0', reasoning_effort: 'high' },
    clientFactory: () => client,
  })
  await host.connect()
  for (const item of items) {
    const result = await host.inspectVisual({ asset_id: item.assetId, preflight_id: item.preflightId })
    assert.equal(result.status, 'inspected_pass')
    assert.equal(result.cached, false)
  }
  const cached = await host.inspectVisual({ asset_id: items[0].assetId, preflight_id: items[0].preflightId })
  await host.close()

  assert.equal(cached.cached, true)
  assert.equal(client.starts.length, 11)
  assert.equal(client.inputs.length, 11)
  assert.equal(client.unsubscribes.length, 11)
  assert.ok(client.inputs.every(input => input.filter(item => item.type === 'localImage').length === 1))
  assert.ok(client.inputs.every(input => input.every(item => item.type !== 'image' && item.type !== 'inputImage')))
  const manifest = await readAssetManifest(workspace)
  assert.equal(manifest.visual_reviews.length, 11)
  assert.ok(manifest.visual_reviews.every(receipt => receipt.reviewer_role === 'independent_visual_review'))
  assert.ok(manifest.visual_reviews.every(receipt => receipt.reviewer.startsWith('independent-thread:')))
})

test('failed preflights may receive pixel diagnostics without creating acceptance evidence', async t => {
  const { workspace, items } = await visualFixture(t, 1, 'svg', { preflightPassed: false })
  const client = new VisualReviewClient()
  const host = new LongWriterHost({
    workspace,
    codexHome: path.join(workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0', reasoning_effort: 'xhigh' },
    clientFactory: () => client,
  })
  await host.connect()
  await assert.rejects(
    host.inspectVisual({ asset_id: items[0].assetId, preflight_id: items[0].preflightId }),
    /requires a passing preflight/,
  )
  const diagnostic = await host.inspectVisual({
    asset_id: items[0].assetId,
    preflight_id: items[0].preflightId,
    diagnostic: true,
  })
  await host.close()

  assert.equal(diagnostic.status, 'diagnosed_pass')
  assert.equal(diagnostic.diagnostic, true)
  assert.equal(diagnostic.review.reviewer_role, 'diagnostic_visual_review')
  assert.equal(client.starts.length, 1)
  assert.equal(client.starts[0].threadSource, 'longwriter-visual-diagnostic')
  assert.match(client.inputs[0][0].text, /Diagnostic mode/)
  assert.match(client.inputs[0][0].text, /Deterministic preflight status: failed/)
  assert.equal(client.inputs[0].filter(item => item.type === 'localImage').length, 1)
  assert.equal((await readAssetManifest(workspace)).visual_reviews.length, 0)
})

test('visual reviewer hash mismatches are rejected and photo previews use the same independent receipt path', async t => {
  const svg = await visualFixture(t, 1)
  const mismatchedClient = new VisualReviewClient({ mismatchField: 'preview_sha256' })
  const mismatchedHost = new LongWriterHost({
    workspace: svg.workspace,
    codexHome: path.join(svg.workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0' },
    clientFactory: () => mismatchedClient,
  })
  await mismatchedHost.connect()
  await assert.rejects(
    mismatchedHost.inspectVisual({ asset_id: svg.items[0].assetId, preflight_id: svg.items[0].preflightId }),
    /mismatched preview_sha256/,
  )
  await mismatchedHost.close()
  assert.equal((await readAssetManifest(svg.workspace)).visual_reviews.length, 0)
  assert.equal(mismatchedClient.unsubscribes.length, 3)

  const photo = await visualFixture(t, 1, 'photo')
  const photoClient = new VisualReviewClient()
  const photoHost = new LongWriterHost({
    workspace: photo.workspace,
    codexHome: path.join(photo.workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0' },
    clientFactory: () => photoClient,
  })
  await photoHost.connect()
  const result = await photoHost.inspectVisual({ asset_id: photo.items[0].assetId, preflight_id: photo.items[0].preflightId })
  await photoHost.close()
  assert.equal(result.status, 'inspected_pass')
})

test('visual reviewer tool use is interrupted, rejected as evidence, and retried once in a fresh thread', async t => {
  const fixture = await visualFixture(t, 1)
  const client = new VisualReviewClient({ toolOnFirstAttempt: true })
  const host = new LongWriterHost({
    workspace: fixture.workspace,
    codexHome: path.join(fixture.workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0', reasoning_effort: 'xhigh' },
    clientFactory: () => client,
  })
  await host.connect()
  const result = await host.inspectVisual({
    asset_id: fixture.items[0].assetId,
    preflight_id: fixture.items[0].preflightId,
  })
  await host.close()

  assert.equal(result.status, 'inspected_pass')
  assert.equal(client.starts.length, 2)
  assert.equal(client.inputs.length, 2)
  assert.equal(client.interrupts.length, 1)
  assert.equal(client.unsubscribes.length, 2)
  assert.equal((await readAssetManifest(fixture.workspace)).visual_reviews.length, 1)
})

test('visual reviewer fail without an actionable finding is rejected and retried', async t => {
  const fixture = await visualFixture(t, 1)
  const client = new VisualReviewClient({ emptyFailOnFirstAttempt: true })
  const host = new LongWriterHost({
    workspace: fixture.workspace,
    codexHome: path.join(fixture.workspace, '.codex-home'),
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0' },
    clientFactory: () => client,
  })
  await host.connect()
  const result = await host.inspectVisual({
    asset_id: fixture.items[0].assetId,
    preflight_id: fixture.items[0].preflightId,
  })
  await host.close()

  assert.equal(result.status, 'inspected_pass')
  assert.equal(client.starts.length, 2)
  assert.equal((await readAssetManifest(fixture.workspace)).visual_reviews.length, 1)
})

class PublicationFlowClient extends EventEmitter {
  constructor(workspace) {
    super()
    this.workspace = workspace
    this.handler = null
    this.goal = null
    this.rootTurns = 0
    this.rootStart = null
    this.rootInputs = []
    this.clarificationResponse = null
    this.approvalResponses = []
    this.interrupts = []
    this.pendingTurn = null
    this.reviewInputs = []
    this.unsubscribes = []
    this.closed = false
  }

  setServerRequestHandler(handler) {
    this.handler = handler
  }

  async start() {}

  async initialize() {
    return { userAgent: 'Codex Desktop/0.151.0 (test)' }
  }

  async close() {
    this.closed = true
  }

  async request(method, params) {
    if (method === 'thread/start') {
      if (params.ephemeral) return { thread: { id: 'review-thread' } }
      this.rootStart = params
      return {
        thread: { id: 'root-thread' },
        sandbox: { type: 'readOnly', networkAccess: false },
      }
    }
    if (method === 'thread/name/set') return {}
    if (method === 'thread/goal/set') {
      this.goal = {
        threadId: params.threadId,
        objective: params.objective ?? this.goal?.objective,
        status: params.status ?? this.goal?.status,
        tokenBudget: null,
        tokensUsed: 0,
        timeUsedSeconds: 0,
      }
      return { goal: this.goal }
    }
    if (method === 'thread/goal/get') return { goal: this.goal }
    if (method === 'turn/start') {
      if (params.threadId === 'review-thread') return this.#reviewTurn(params)
      return this.#rootTurn(params)
    }
    if (method === 'turn/interrupt') {
      this.interrupts.push(params)
      assert.equal(this.pendingTurn?.id, params.turnId)
      const turn = { ...this.pendingTurn, status: 'interrupted' }
      this.pendingTurn = null
      this.emit('notification', { method: 'turn/completed', params: { threadId: params.threadId, turn } })
      return {}
    }
    if (method === 'thread/unsubscribe') {
      this.unsubscribes.push(params.threadId)
      return { status: 'unsubscribed' }
    }
    throw new Error(`unexpected fake-client request: ${method}`)
  }

  async #callTool(turnId, tool, args) {
    const response = await this.handler({
      method: 'item/tool/call',
      params: {
        threadId: 'root-thread',
        turnId,
        callId: `${turnId}-${tool}`,
        namespace: null,
        tool,
        arguments: args,
      },
    })
    assert.equal(response.success, true, response.contentItems?.[0]?.text)
    return JSON.parse(response.contentItems[0].text)
  }

  async #rootTurn(params) {
    this.rootTurns += 1
    const turnId = `root-turn-${this.rootTurns}`
    this.rootInputs.push(params.input)
    if (this.rootTurns === 1) {
      this.clarificationResponse = await this.handler({
        method: 'item/tool/requestUserInput',
        params: {
          threadId: 'root-thread',
          turnId,
          itemId: 'question-1',
          isBlocking: true,
          autoResolutionMs: null,
          questions: [{
            id: 'audience',
            header: 'Audience',
            question: 'Who is the intended reader?',
            isOther: true,
            isSecret: false,
            options: [{ label: 'Medical students', description: 'Use introductory clinical language.' }],
          }],
        },
      })
      for (const method of ['item/commandExecution/requestApproval', 'item/fileChange/requestApproval']) {
        this.approvalResponses.push(await this.handler({ method, params: {} }))
      }
      this.approvalResponses.push(await this.handler({ method: 'item/permissions/requestApproval', params: {} }))
      this.approvalResponses.push(await this.handler({ method: 'mcpServer/elicitation/request', params: {} }))
      await this.#callTool(turnId, 'initialize_publication', { project: {
        title: 'Lead geometry',
        objective: 'Explain ECG leads from first principles',
        audience: 'medical students',
        language: 'English',
        sections: [{ id: 'chapter', title: 'Lead geometry', objective: 'Explain lead projection', target_words: 40 }],
        quality_contract: {
          minimum_section_ratio: 0.75,
          maximum_section_ratio: 4,
          minimum_total_ratio: 0.75,
          maximum_total_ratio: 4,
          long_sentence_chars: 80,
          maximum_long_sentence_ratio: 1,
          minimum_review_score: 85,
        },
        visual_contract: {
          schema_version: 1,
          figure_start: 1,
          minimum_figures: 0,
          required_sections: [],
          figures: [],
        },
        research_contract: { minimum_image_searches: 0, minimum_image_candidates: 0 },
      } })
    } else if (this.rootTurns === 2) {
      await this.#callTool(turnId, 'commit_chunk', {
        section_id: 'chapter',
        chunk_id: 'chapter-01',
        markdown: 'An ECG electrode touches the body and samples electric potential at one location. A lead is not that wire or electrode. It is a defined voltage comparison between sensing locations. The lead axis supplies a direction, so the heart vector contributes according to its projection onto that axis. This distinction connects placement, reference potential, polarity, and waveform amplitude without treating the tracing as a direct picture of the heart.',
      })
    } else if (this.rootTurns === 3) {
      const result = await this.#callTool(turnId, 'finalize_publication', {})
      assert.equal(result.finalized, true, JSON.stringify(result))
    } else {
      throw new Error('fake flow exceeded expected root turns')
    }
    this.pendingTurn = {
      id: turnId,
      status: 'inProgress',
      items: [{ type: 'agentMessage', id: `${turnId}-message`, text: 'done' }],
    }
    return { turn: { id: turnId } }
  }

  async #reviewTurn(params) {
    assert.ok(params.outputSchema)
    this.reviewInputs.push(params.input)
    assert.deepEqual(params.input.map(item => item.type), ['text'])
    const expectedHash = params.input[0].text.match(/Expected article SHA-256: ([a-f0-9]{64})/)?.[1]
    const visualAuditHash = params.input[0].text.match(/Expected visual-audit SHA-256: ([a-f0-9]{64})/)?.[1]
    assert.ok(expectedHash)
    assert.ok(visualAuditHash)
    const review = {
      article_sha256: expectedHash,
      visual_audit_sha256: visualAuditHash,
      visual_audit_passed: true,
      verdict: 'pass',
      overall_score: 95,
      summary: 'The explanation is coherent and evidence-disciplined.',
      critical_issues: [],
      section_findings: [{ section_id: 'chapter', score: 95, findings: [] }],
      visual_findings: [],
      recommended_next_action: 'Finalize.',
    }
    const turn = {
      id: 'review-turn',
      status: 'completed',
      items: [{ type: 'agentMessage', id: 'review-message', text: JSON.stringify(review) }],
    }
    this.emit('notification', { method: 'turn/completed', params: { threadId: 'review-thread', turn } })
    return { turn: { id: turn.id } }
  }
}

test('host integrates clarification, native image input, approvals, goal rounds, reviewer, and finalize', async t => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-host-flow-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  const image = path.join(workspace, 'reference.png')
  await writeFile(image, Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  const client = new PublicationFlowClient(workspace)
  const questionCalls = []
  const host = new LongWriterHost({
    workspace,
    codexHome: path.join(workspace, '.codex-home'),
    config: {
      model: 'test-model',
      model_provider: 'test-provider',
      codex_cli_version: '0.151.0',
      sandbox: 'read-only',
      approval_policy: 'never',
      approvals_reviewer: 'auto_review',
      max_turns: 8,
    },
    clientFactory: () => client,
    answerQuestions: async questions => {
      questionCalls.push(questions)
      return { answers: { audience: { answers: ['Medical students'] } } }
    },
  })
  const result = await host.start('Create a concise ECG lead explanation.', [image])
  await host.close()

  assert.equal(result.goal.status, 'complete')
  assert.equal(result.rounds, 3)
  assert.equal(client.interrupts.length, 3)
  assert.equal(questionCalls.length, 1)
  assert.deepEqual(client.clarificationResponse, { answers: { audience: { answers: ['Medical students'] } } })
  assert.deepEqual(client.approvalResponses[0], { decision: 'decline' })
  assert.deepEqual(client.approvalResponses[1], { decision: 'decline' })
  assert.deepEqual(client.approvalResponses[2], { permissions: {}, scope: 'turn', strictAutoReview: true })
  assert.deepEqual(client.approvalResponses[3], { action: 'decline', content: null, _meta: null })
  assert.equal(client.rootStart.sandbox, 'read-only')
  assert.equal(client.rootStart.approvalPolicy, 'never')
  assert.equal(client.rootStart.dynamicTools.length, 17)
  assert.deepEqual(client.rootInputs[0][1], { type: 'localImage', path: image })
  assert.equal(client.reviewInputs.length, 1)
  assert.deepEqual(client.unsubscribes, ['review-thread'])
  assert.equal(client.closed, true)
  assert.equal((await publicationStatus(workspace)).chunks, 1)
})

class FailedTurnClient extends EventEmitter {
  constructor() {
    super()
    this.handler = null
    this.goal = null
  }

  setServerRequestHandler(handler) { this.handler = handler }
  async start() {}
  async initialize() { return { userAgent: 'Codex Desktop/0.151.0 (test)' } }
  async close() {}

  async request(method, params) {
    if (method === 'thread/start') return { thread: { id: 'failed-root-thread' } }
    if (method === 'thread/name/set') return {}
    if (method === 'thread/goal/set') {
      this.goal = { threadId: params.threadId, objective: params.objective, status: params.status }
      return { goal: this.goal }
    }
    if (method === 'thread/goal/get') return { goal: { ...this.goal, status: 'blocked' } }
    if (method === 'turn/start') {
      const turn = { id: 'failed-turn', status: 'failed', error: { message: 'HTTP 413 Payload Too Large' }, items: [] }
      this.emit('notification', { method: 'turn/completed', params: { threadId: params.threadId, turn } })
      return { turn: { id: turn.id } }
    }
    throw new Error(`unexpected failed-turn request: ${method}`)
  }
}

test('failed runs persist the final blocked goal, finished timestamp, and exit code', async t => {
  const runDirectory = await mkdtemp(path.join(os.tmpdir(), 'longwriter-failed-run-'))
  t.after(() => rm(runDirectory, { recursive: true, force: true }))
  const workspace = path.join(runDirectory, 'workspace')
  await writeFile(path.join(runDirectory, 'task.txt'), 'Synthetic failure.')
  const recorder = new RunRecorder(runDirectory)
  await recorder.create({
    status: 'prepared',
    task_file: path.join(runDirectory, 'task.txt'),
    config_file: path.join(runDirectory, 'config.json'),
    workspace,
    rounds_completed: 0,
  })
  const client = new FailedTurnClient()
  const host = new LongWriterHost({
    workspace,
    codexHome: path.join(runDirectory, '.codex-home'),
    recorder,
    config: { model: 'test-model', model_provider: 'test-provider', codex_cli_version: '0.151.0' },
    clientFactory: () => client,
  })
  await assert.rejects(host.start('Fail once.'), /ended with status failed/)
  await host.close()
  const state = await recorder.load()
  assert.equal(state.status, 'failed')
  assert.equal(state.goal.status, 'blocked')
  assert.equal(state.exit_code, 1)
  assert.equal(state.active_round, null)
  assert.ok(state.failed_at)
  assert.equal(state.finished_at, state.failed_at)
})

test('run recorder serializes concurrent state updates without temporary-file races', async t => {
  const runDirectory = await mkdtemp(path.join(os.tmpdir(), 'longwriter-recorder-race-'))
  t.after(() => rm(runDirectory, { recursive: true, force: true }))
  const recorder = new RunRecorder(runDirectory)
  await recorder.create({
    status: 'prepared',
    task_file: path.join(runDirectory, 'task.txt'),
    config_file: path.join(runDirectory, 'config.json'),
    workspace: path.join(runDirectory, 'workspace'),
  })
  await Promise.all(Array.from({ length: 24 }, (_, index) => recorder.update({ [`concurrent_${index}`]: index })))
  await recorder.flush()
  const state = await recorder.load()
  for (let index = 0; index < 24; index += 1) assert.equal(state[`concurrent_${index}`], index)
})
