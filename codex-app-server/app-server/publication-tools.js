import {
  appendVisualPreflight,
  commitChunk,
  initializeProject,
  publicationStatus,
  readAssetManifest,
  readProject,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
  reviseChunk,
  setVisualContract,
} from '../lib/project-store.js'
import { runValidator } from '../lib/validator-runner.js'
import { applyImage } from '../image/index.js'
import { applyMermaid } from '../mermaid/index.js'
import { applySvg } from '../svg/index.js'
import { projectPublicationGoal } from './policy.js'

const TERMINAL_TOOLS = new Set([
  'initialize_publication',
  'plan_visuals',
  'svg_delegate',
  'commit_chunk',
  'revise_chunk',
  'review_publication',
  'finalize_publication',
])

function jsonSchema(parameters = {}) {
  const properties = {}
  const required = []
  for (const [name, parameter] of Object.entries(parameters)) {
    const property = parameter.type === 'json' ? {} : { type: parameter.type }
    if (parameter.description) property.description = parameter.description
    properties[name] = property
    if (parameter.required) required.push(name)
  }
  return {
    type: 'object',
    additionalProperties: false,
    properties,
    ...(required.length === 0 ? {} : { required }),
  }
}

function asToolSpec(definition) {
  return {
    type: 'function',
    name: definition.name,
    description: definition.description,
    inputSchema: definition.inputSchema ?? jsonSchema(definition.parameters),
  }
}

function normalizeToolArguments(definition, rawArgs) {
  const args = { ...(rawArgs ?? {}) }
  for (const [name, parameter] of Object.entries(definition.parameters ?? {})) {
    if (parameter.type !== 'json' || typeof args[name] !== 'string') continue
    try {
      args[name] = JSON.parse(args[name])
    } catch (error) {
      throw new TypeError(`${name} must be valid JSON when encoded as a string: ${error.message}`)
    }
  }
  return args
}

function successfulReview(review, expectedHash, minimumScore) {
  return review?.article_sha256 === expectedHash
    && review?.visual_audit_passed === true
    && review?.verdict === 'pass'
    && typeof review?.overall_score === 'number'
    && review.overall_score >= minimumScore
    && Array.isArray(review?.critical_issues)
    && review.critical_issues.length === 0
    && Array.isArray(review?.visual_findings)
}

export class PublicationToolRuntime {
  constructor(options) {
    this.workspace = options.workspace
    this.setGoal = options.setGoal
    this.completeGoal = options.completeGoal
    this.requestReview = options.requestReview
    this.inspectVisual = options.inspectVisual
    this.delegateSvg = options.delegateSvg
    this.svgStatus = options.svgStatus
    this.collectSvg = options.collectSvg
    this.waitForSvg = options.waitForSvg
    this.definitions = new Map()
    this.terminalByTurn = new Map()
    this.manuscriptMutationByTurn = new Set()
    this.#registerTools()
  }

  specs() {
    return [...this.definitions.values()].map(asToolSpec)
  }

  async execute(tool, args, context) {
    const definition = this.definitions.get(tool)
    if (!definition) throw new Error(`unknown LongMDWriter tool: ${tool}`)
    const normalizedArgs = normalizeToolArguments(definition, args)
    const priorTerminal = this.terminalByTurn.get(context.turnId)
    if (priorTerminal && TERMINAL_TOOLS.has(tool)) {
      throw new Error(`turn already completed its publication unit through ${priorTerminal}; finish the turn now`)
    }
    if ((tool === 'commit_chunk' || tool === 'revise_chunk') && this.manuscriptMutationByTurn.has(context.turnId)) {
      throw new Error('at most one manuscript mutation is allowed per turn')
    }
    const result = await definition.execute(normalizedArgs, {
      workspace: this.workspace,
      signal: context.signal,
      threadId: context.threadId,
      turnId: context.turnId,
    })
    if (tool === 'commit_chunk' || tool === 'revise_chunk') this.manuscriptMutationByTurn.add(context.turnId)
    if (TERMINAL_TOOLS.has(tool)) this.terminalByTurn.set(context.turnId, tool)
    return {
      ...result,
      ...(TERMINAL_TOOLS.has(tool) ? { turn_complete: true, instruction: 'Finish this turn now.' } : {}),
    }
  }

  terminalToolForTurn(turnId) {
    return this.terminalByTurn.get(turnId) ?? null
  }

  #register(definition) {
    if (this.definitions.has(definition.name)) throw new Error(`duplicate tool: ${definition.name}`)
    this.definitions.set(definition.name, definition)
  }

  #registerTools() {
    this.#register({
      name: 'initialize_publication',
      description: 'Initialize the canonical LongMDWriter workspace from a complete project contract and replace the provisional thread goal with a precise publication goal.',
      inputSchema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          project: {
            type: 'object',
            additionalProperties: true,
            properties: {
              title: { type: 'string' },
              objective: { type: 'string' },
              audience: { type: 'string' },
              language: { type: 'string' },
              sections: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: true,
                  properties: {
                    id: { type: 'string' },
                    title: { type: 'string' },
                    objective: { type: 'string' },
                    target_words: { type: 'integer', minimum: 1 },
                  },
                  required: ['id', 'title', 'objective', 'target_words'],
                },
              },
              visual_contract: {
                type: 'object',
                additionalProperties: false,
                properties: {
                  schema_version: { type: 'integer', enum: [2] },
                  figure_start: { type: 'integer', minimum: 1 },
                  minimum_figures: { type: 'integer', minimum: 0 },
                  required_sections: { type: 'array', items: { type: 'string' } },
                  figures: { type: 'array', maxItems: 0 },
                },
                required: ['schema_version', 'figure_start', 'minimum_figures', 'required_sections', 'figures'],
              },
              quality_contract: {
                type: 'object',
                additionalProperties: false,
                properties: {
                  minimum_section_ratio: { type: 'number', exclusiveMinimum: 0, maximum: 1.5 },
                  maximum_section_ratio: { type: 'number', minimum: 1, maximum: 4 },
                  minimum_total_ratio: { type: 'number', exclusiveMinimum: 0, maximum: 1.5 },
                  maximum_total_ratio: { type: 'number', minimum: 1, maximum: 4 },
                  long_sentence_chars: { type: 'integer', minimum: 1, maximum: 500 },
                  maximum_long_sentence_ratio: { type: 'number', minimum: 0, maximum: 1 },
                  minimum_review_score: { type: 'integer', minimum: 1, maximum: 100 },
                  require_zero_placeholders: { type: 'boolean' },
                  require_review: { type: 'boolean' },
                },
                required: [
                  'minimum_section_ratio',
                  'maximum_section_ratio',
                  'minimum_total_ratio',
                  'maximum_total_ratio',
                  'long_sentence_chars',
                  'maximum_long_sentence_ratio',
                  'minimum_review_score',
                ],
              },
              research_contract: {
                type: 'object',
                additionalProperties: false,
                properties: {
                  minimum_image_searches: { type: 'integer', minimum: 0 },
                  minimum_image_candidates: { type: 'integer', minimum: 0 },
                },
                required: ['minimum_image_searches', 'minimum_image_candidates'],
              },
            },
            required: [
              'title',
              'objective',
              'audience',
              'language',
              'sections',
              'visual_contract',
              'quality_contract',
              'research_contract',
            ],
          },
        },
        required: ['project'],
      },
      execute: async args => {
        if (!args.project || typeof args.project !== 'object' || Array.isArray(args.project)) {
          throw new TypeError('initialize_publication requires a project object')
        }
        if (!args.project.visual_contract || !Array.isArray(args.project.visual_contract.figures)) {
          throw new TypeError('initialize_publication requires an explicit visual_contract with an empty figures array')
        }
        if (args.project.visual_contract.figures.length !== 0) {
          throw new Error('initialize_publication may set visual requirements only; figures must be empty until research completes and plan_visuals is called')
        }
        if (!args.project.quality_contract || typeof args.project.quality_contract !== 'object') {
          throw new TypeError('initialize_publication requires an explicit quality_contract')
        }
        if (!args.project.research_contract || typeof args.project.research_contract !== 'object') {
          throw new TypeError('initialize_publication requires an explicit research_contract')
        }
        const initialized = await initializeProject(this.workspace, args.project)
        const goal = await this.setGoal(projectPublicationGoal(initialized.project), 'active')
        return { created: initialized.created, goal, status: initialized.status }
      },
    })

    this.#register({
      name: 'plan_visuals',
      description: 'Atomically fill project.json.visual_contract without weakening its initialized schema version, figure-start, minimum-count, or required-section constraints. Each figure needs its contiguous number, id, section_id, kind, purpose, required_labels, optional review_required, and a design_brief containing figure_type, publication_width, scientific_claim, scientific_checks, and reading_order.',
      parameters: {
        visual_contract: { type: 'json', required: true, description: 'Visual contract object with a figures array.' },
      },
      execute: async args => ({ planned: true, visual_contract: await setVisualContract(this.workspace, args.visual_contract) }),
    })

    this.#register({
      name: 'publication_status',
      description: 'Read deterministic manuscript progress, section word counts, chunk ids, visual state, asynchronous SVG job summaries, and current article SHA-256.',
      parameters: {},
      execute: async () => ({
        ...(await publicationStatus(this.workspace)),
        ...(typeof this.svgStatus === 'function' ? { svg_jobs: this.svgStatus().jobs } : {}),
      }),
    })

    this.#register({
      name: 'inspect_visual',
      description: 'Ask a separate ephemeral reviewer thread to inspect exactly one registered retained PNG preview. The host validates and records a hash-bound independent visual review, then returns only compact text and hashes to this root thread; image bytes never enter the durable root history.',
      parameters: {
        asset_id: { type: 'string', required: true, description: 'Current registered planned asset id.' },
        preflight_id: { type: 'string', required: true, description: 'Passing preflight id bound to the current asset and retained PNG preview.' },
      },
      execute: async (args, exec) => {
        if (typeof this.inspectVisual !== 'function') throw new Error('inspect_visual is unavailable without a host visual reviewer')
        return this.inspectVisual({ asset_id: args.asset_id, preflight_id: args.preflight_id, signal: exec.signal })
      },
    })

    this.#register({
      name: 'svg_delegate',
      description: 'Start one bounded asynchronous SVG worker job for an existing kind=svg visual plan and return immediately with a job id. A successful delegation completes the current root turn so the host can schedule the next independent unit. The host uses fresh isolated illustrator threads, an in-memory id-addressed svg_edit tool for every revision, deterministic preflight, independent visual review, a monotonic locked-pass ledger, a best-candidate baseline, and a bounded number of job generations per plan. Do not delegate the same active plan twice.',
      parameters: {
        visual_plan_id: { type: 'string', required: true, description: 'Existing kind=svg visual plan id.' },
      },
      execute: async args => {
        if (typeof this.delegateSvg !== 'function') throw new Error('svg_delegate is unavailable without an SVG job manager')
        return this.delegateSvg(args.visual_plan_id)
      },
    })

    this.#register({
      name: 'svg_status',
      description: 'Read compact progress for one asynchronous SVG job, or all jobs when job_id is omitted. This never mutates publication state.',
      parameters: {
        job_id: { type: 'string', description: 'Optional SVG job id returned by svg_delegate.' },
      },
      execute: async args => {
        if (typeof this.svgStatus !== 'function') throw new Error('svg_status is unavailable without an SVG job manager')
        return this.svgStatus(args.job_id ?? '')
      },
    })

    this.#register({
      name: 'svg_wait',
      description: 'Wait briefly for an asynchronous SVG job state change only when no independent prose or research work remains. Returns after a change or the bounded timeout.',
      parameters: {
        job_id: { type: 'string', description: 'Optional SVG job id; omit to wait for any active SVG job.' },
        timeout_seconds: { type: 'integer', description: 'Bounded wait from 1 to 30 seconds; defaults to 15.' },
      },
      execute: async args => {
        if (typeof this.waitForSvg !== 'function') throw new Error('svg_wait is unavailable without an SVG job manager')
        const seconds = args.timeout_seconds ?? 15
        if (!Number.isSafeInteger(seconds) || seconds < 1 || seconds > 30) {
          throw new TypeError('svg_wait timeout_seconds must be an integer in 1..30')
        }
        return this.waitForSvg(args.job_id ?? '', seconds * 1000)
      },
    })

    this.#register({
      name: 'svg_collect',
      description: 'Return the registered asset metadata for a passing asynchronous SVG job. It never returns image bytes and never treats a running or failed job as ready.',
      parameters: {
        job_id: { type: 'string', required: true, description: 'SVG job id returned by svg_delegate.' },
      },
      execute: async args => {
        if (typeof this.collectSvg !== 'function') throw new Error('svg_collect is unavailable without an SVG job manager')
        return this.collectSvg(args.job_id)
      },
    })

    this.#register({
      name: 'commit_chunk',
      description: 'Atomically append one coherent Markdown chunk to a planned section. A successful call completes the current publication turn.',
      parameters: {
        section_id: { type: 'string', required: true, description: 'Existing section id.' },
        chunk_id: { type: 'string', required: true, description: 'Globally unique stable chunk id.' },
        markdown: { type: 'string', required: true, description: 'Substantive Markdown without LongWriter control markers.' },
      },
      execute: async args => ({ committed: true, chunk_id: args.chunk_id, status: await commitChunk(this.workspace, args) }),
    })

    this.#register({
      name: 'revise_chunk',
      description: 'Atomically replace one complete existing manuscript chunk. A successful call completes the current publication turn.',
      parameters: {
        chunk_id: { type: 'string', required: true, description: 'Existing stable chunk id.' },
        markdown: { type: 'string', required: true, description: 'Complete replacement Markdown without control markers.' },
      },
      execute: async args => ({ revised: true, chunk_id: args.chunk_id, status: await reviseChunk(this.workspace, args) }),
    })

    this.#register({
      name: 'review_publication',
      description: 'Run deterministic validation; only when it passes, run a fresh read-only Codex reviewer thread with no author transcript. Returns validation evidence and, when eligible, a SHA-bound structured audit.',
      parameters: {
        focus: { type: 'string', description: 'Optional concise review focus.' },
      },
      execute: async (args, exec) => {
        const validator = await runValidator(this.workspace, exec.signal)
        if (!validator.passed) {
          return {
            reviewed: false,
            reason: 'deterministic-validation-failed',
            validator,
          }
        }
        const review = await this.requestReview({ validator, focus: args.focus ?? '', signal: exec.signal })
        return { reviewed: true, validator, review }
      },
    })

    this.#register({
      name: 'finalize_publication',
      description: 'Validate and independently review the exact current article. This is the only tool allowed to complete the Codex thread goal.',
      parameters: {},
      execute: async (_args, exec) => {
        const activeSvgJobs = typeof this.svgStatus === 'function'
          ? this.svgStatus().jobs.filter(job => ['queued', 'running', 'revising'].includes(job.status))
          : []
        if (activeSvgJobs.length > 0) {
          return {
            finalized: false,
            reason: 'svg-jobs-pending',
            pending_svg_jobs: activeSvgJobs,
          }
        }
        const project = await readProject(this.workspace)
        const validator = await runValidator(this.workspace, exec.signal)
        if (!validator.passed) {
          return { finalized: false, reason: 'deterministic-validation-failed', validator }
        }
        const review = await this.requestReview({ validator, focus: '', signal: exec.signal })
        const expectedHash = validator.metrics?.article_sha256
        const minimumScore = project.quality_contract.minimum_review_score
        if (!successfulReview(review, expectedHash, minimumScore)) {
          return {
            finalized: false,
            reason: 'independent-review-failed',
            expected_article_sha256: expectedHash,
            minimum_review_score: minimumScore,
            validator,
            review,
          }
        }
        const goal = await this.completeGoal()
        return { finalized: true, article_sha256: expectedHash, validator, review, goal }
      },
    })

    const dependencies = {
      workspace: exec => exec.workspace,
      registerAsset,
      resolveVisualPlan,
      readRegisteredAsset,
      readAssetManifest,
      appendVisualPreflight,
      authorizeSvgSubmit: args => {
        const jobs = typeof this.svgStatus === 'function' ? this.svgStatus().jobs : []
        const delegated = jobs.find(job => job.visual_plan_id === args.visual_plan_id)
        if (delegated) {
          throw new Error(`svg_submit is unavailable for delegated visual plan ${args.visual_plan_id}; preserve job ${delegated.id} and use only its retained svg_edit revision chain`)
        }
      },
    }
    applySvg(definition => this.#register(definition), dependencies)
    applyMermaid(definition => this.#register(definition), dependencies)
    applyImage(definition => this.#register(definition), dependencies)
  }
}
