import { createHash, randomUUID } from 'node:crypto'

import {
  appendVisualPreflight,
  readAssetManifest,
  readProject,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
} from '../lib/project-store.js'
import { DESIGN_CHECK_KEYS } from '../svg/design.js'
import { submitSvg } from '../svg/submit.js'
import { preflightAsset } from '../svg/workflow.js'

const ACTIVE_STATUSES = new Set(['queued', 'running', 'revising'])
const TERMINAL_STATUSES = new Set(['passed', 'failed'])
const SAFE_JOB_ID = /^svg-job-[a-f0-9-]+$/

export const SVG_WORKER_OUTPUT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    svg: { type: 'string' },
    caption: { type: 'string' },
    alt_text: { type: 'string' },
    change_summary: { type: 'string' },
  },
  required: ['svg', 'caption', 'alt_text', 'change_summary'],
}

export const SVG_WORKER_REVISION_OUTPUT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    caption: { type: 'string' },
    alt_text: { type: 'string' },
    change_summary: { type: 'string' },
    edit_revision: { type: 'integer', minimum: 1 },
  },
  required: ['caption', 'alt_text', 'change_summary', 'edit_revision'],
}

function now() {
  return new Date().toISOString()
}

function boundedInteger(value, fallback, minimum, maximum, name) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isSafeInteger(resolved) || resolved < minimum || resolved > maximum) {
    throw new TypeError(`${name} must be an integer in ${minimum}..${maximum}`)
  }
  return resolved
}

function normalizedText(value, name, maximum) {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${name} must be non-empty text`)
  const resolved = value.trim()
  if (resolved.length > maximum) throw new TypeError(`${name} must contain at most ${maximum} characters`)
  return resolved
}

function uniqueText(values = []) {
  return [...new Set(values.filter(value => typeof value === 'string' && value.trim()).map(value => value.trim()))]
}

function currentVisualAsset(manifest, visualPlanId) {
  const candidates = manifest.assets.filter(asset => asset?.visual_plan_id === visualPlanId)
  if (candidates.length === 0) return null
  const superseded = new Set(candidates.map(asset => asset.supersedes_asset_id).filter(Boolean))
  const tips = candidates.filter(asset => !superseded.has(asset.id))
  return tips.length === 1 ? tips[0] : null
}

function reviewReceipt(evaluation) {
  return evaluation.review?.receipt ?? null
}

function diagnosticReview(evaluation) {
  return evaluation.diagnostic?.review ?? null
}

export function candidateFitness(evaluation = {}) {
  const submission = evaluation.submission ?? {}
  const preflight = evaluation.preflight ?? {}
  const review = reviewReceipt(evaluation)
  const registered = submission.registered === true
  const preflightPassed = preflight.status === 'passed'
  const reviewPassed = review?.verdict === 'pass'
  const scientificPasses = (review?.scientific_checks ?? []).filter(item => item?.verdict === 'pass').length
  const designPasses = DESIGN_CHECK_KEYS.filter(key => review?.design_checks?.[key] === 'pass').length
  const checkedLabels = uniqueText(review?.checked_labels ?? []).length
  const preflightLabels = (preflight.report?.required_labels ?? []).filter(item => item?.present === true).length
  const issueCount = Array.isArray(preflight.report?.issues) ? preflight.report.issues.length : 1000
  const coreScore = Number.isFinite(submission.score) ? submission.score : 0
  return {
    tier: reviewPassed ? 4 : review ? 3 : preflightPassed ? 2 : registered ? 1 : 0,
    passed_checks: scientificPasses + designPasses + Math.max(checkedLabels, preflightLabels),
    issue_count: issueCount,
    core_score: coreScore,
  }
}

export function compareFitness(left, right) {
  if (!right) return 1
  for (const [key, direction] of [['tier', 1], ['passed_checks', 1], ['issue_count', -1], ['core_score', 1]]) {
    const delta = (left?.[key] ?? 0) - (right?.[key] ?? 0)
    if (delta !== 0) return Math.sign(delta) * direction
  }
  return 0
}

export function locksFromEvaluation(evaluation = {}) {
  const preflight = evaluation.preflight ?? {}
  const review = reviewReceipt(evaluation)
  return {
    preflight_passed: preflight.status === 'passed',
    labels: uniqueText([
      ...(preflight.report?.required_labels ?? []).filter(item => item?.present === true).map(item => item.label),
      ...(review?.checked_labels ?? []),
    ]),
    scientific_checks: uniqueText((review?.scientific_checks ?? [])
      .filter(item => item?.verdict === 'pass')
      .map(item => item.criterion)),
    design_checks: uniqueText(DESIGN_CHECK_KEYS.filter(key => review?.design_checks?.[key] === 'pass')),
  }
}

function mergeLocks(left = {}, right = {}) {
  return {
    preflight_passed: left.preflight_passed === true || right.preflight_passed === true,
    labels: uniqueText([...(left.labels ?? []), ...(right.labels ?? [])]),
    scientific_checks: uniqueText([...(left.scientific_checks ?? []), ...(right.scientific_checks ?? [])]),
    design_checks: uniqueText([...(left.design_checks ?? []), ...(right.design_checks ?? [])]),
  }
}

export function lockRegressions(locked = {}, evaluation = {}) {
  const current = locksFromEvaluation(evaluation)
  const regressions = []
  if (locked.preflight_passed === true && current.preflight_passed !== true) {
    regressions.push('deterministic preflight no longer passes')
  }
  for (const [key, label] of [
    ['labels', 'required label'],
    ['scientific_checks', 'scientific check'],
    ['design_checks', 'design check'],
  ]) {
    const present = new Set(current[key] ?? [])
    for (const value of locked[key] ?? []) {
      if (!present.has(value)) regressions.push(`${label} regressed: ${value}`)
    }
  }
  return regressions
}

function feedbackFromEvaluation(evaluation = {}) {
  const submission = evaluation.submission ?? {}
  if (submission.registered !== true) {
    return uniqueText([
      submission.reason,
      ...(submission.errors ?? []),
      ...(submission.signals ?? []),
    ]).slice(0, 20)
  }
  const preflight = evaluation.preflight ?? {}
  if (preflight.status !== 'passed') {
    const diagnostic = diagnosticReview(evaluation)
    const diagnosticFeedback = uniqueText([
      diagnostic?.summary ? `visual diagnosis: ${diagnostic.summary}` : '',
      ...(diagnostic?.findings ?? []).map(item => `visual finding: ${item}`),
      ...(diagnostic?.scientific_checks ?? [])
        .filter(item => item?.verdict === 'fail')
        .map(item => `visual scientific failure: ${item.criterion}`),
      ...DESIGN_CHECK_KEYS
        .filter(key => diagnostic?.design_checks?.[key] === 'fail')
        .map(key => `visual design failure: ${key}`),
    ]).slice(0, 6)
    return uniqueText([
      preflight.reason,
      ...(preflight.report?.issues ?? []).slice(0, 12),
      ...diagnosticFeedback,
      ...(preflight.report?.warnings ?? []).slice(0, 2),
    ]).slice(0, 20)
  }
  const review = reviewReceipt(evaluation)
  if (review?.verdict !== 'pass') {
    return uniqueText([
      review?.summary,
      ...(review?.findings ?? []),
      ...(review?.scientific_checks ?? [])
        .filter(item => item?.verdict === 'fail')
        .map(item => `scientific check failed: ${item.criterion}`),
      ...DESIGN_CHECK_KEYS
        .filter(key => review?.design_checks?.[key] === 'fail')
        .map(key => `design check failed: ${key}`),
    ]).slice(0, 20)
  }
  return []
}

function failureSignature(feedback) {
  return createHash('sha256').update(JSON.stringify([...feedback].sort()), 'utf8').digest('hex').slice(0, 20)
}

function sourceSha256(svg) {
  return createHash('sha256').update(svg, 'utf8').digest('hex')
}

function safeSnapshot(job) {
  return JSON.parse(JSON.stringify(job))
}

function publicJob(job) {
  if (!job) return null
  return {
    id: job.id,
    visual_plan_id: job.visual_plan_id,
    status: job.status,
    attempts: job.attempts,
    maximum_attempts: job.maximum_attempts,
    generation: job.generation,
    maximum_generations: job.maximum_generations,
    stagnation_count: job.stagnation_count,
    strategy: job.strategy,
    best: job.best ?? null,
    locked_constraints: job.locked_constraints,
    last_feedback: job.last_feedback,
    last_worker_thread_id: job.last_worker_thread_id ?? null,
    created_at: job.created_at,
    updated_at: job.updated_at,
  }
}

export class SvgJobManager {
  constructor(options = {}) {
    this.workspace = options.workspace
    this.recorder = options.recorder ?? null
    this.startWorker = options.startWorker
    this.runWorker = options.runWorker
    this.disposeWorker = options.disposeWorker ?? (async () => {})
    this.inspectVisual = options.inspectVisual
    this.diagnoseVisual = options.diagnoseVisual ?? null
    this.processCandidate = options.processCandidate ?? (input => this.#processCandidate(input))
    this.readRegisteredAsset = options.readRegisteredAsset ?? readRegisteredAsset
    this.readProject = options.readProject ?? readProject
    this.readAssetManifest = options.readAssetManifest ?? readAssetManifest
    this.maxConcurrent = boundedInteger(options.maxConcurrent, 2, 1, 6, 'svg worker maxConcurrent')
    this.maxAttempts = boundedInteger(options.maxAttempts, 8, 1, 20, 'svg worker maxAttempts')
    this.stagnationLimit = boundedInteger(options.stagnationLimit, 2, 1, 5, 'svg worker stagnationLimit')
    this.maxJobsPerPlan = boundedInteger(options.maxJobsPerPlan, 3, 1, 10, 'svg worker maxJobsPerPlan')
    this.jobs = new Map()
    this.activeCount = 0
    this.activeRuns = new Set()
    this.stopping = false
    this.version = 0
    this.waiters = new Set()
  }

  async restore() {
    const saved = this.recorder?.state?.svg_jobs ?? {}
    const generations = new Map()
    const entries = Object.entries(saved)
      .sort((left, right) => String(left[1]?.created_at ?? '').localeCompare(String(right[1]?.created_at ?? '')))
    for (const [id, value] of entries) {
      if (!SAFE_JOB_ID.test(id) || !value || typeof value !== 'object') continue
      const job = safeSnapshot(value)
      const generation = (generations.get(job.visual_plan_id) ?? 0) + 1
      generations.set(job.visual_plan_id, generation)
      job.generation = Number.isSafeInteger(job.generation) ? job.generation : generation
      job.maximum_generations = this.maxJobsPerPlan
      if (ACTIVE_STATUSES.has(job.status)) {
        job.status = 'queued'
        job.updated_at = now()
        job.last_feedback = uniqueText([
          ...(job.best?.actionable_feedback ?? job.last_feedback ?? []),
          'The previous host process ended before this SVG job completed; resume from the retained best candidate.',
        ])
      }
      this.jobs.set(id, job)
    }
    await this.#persist()
    this.#schedulePump()
  }

  async delegate(visualPlanId) {
    const plan = await resolveVisualPlan(this.workspace, visualPlanId)
    if (plan.kind !== 'svg') throw new Error(`svg_delegate requires an SVG visual plan, received kind=${plan.kind}`)
    const existing = [...this.jobs.values()].find(job => job.visual_plan_id === plan.id && ACTIVE_STATUSES.has(job.status))
    if (existing) return { delegated: false, reason: 'already_active', job: publicJob(existing) }
    const planJobs = [...this.jobs.values()].filter(job => job.visual_plan_id === plan.id)
    if (planJobs.length >= this.maxJobsPerPlan) {
      const latest = planJobs.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)))[0]
      throw new Error(`SVG plan ${plan.id} exhausted its bounded ${this.maxJobsPerPlan}-job generation budget; retained champion is ${latest?.best?.asset_id ?? 'unavailable'}`)
    }
    const id = `svg-job-${randomUUID()}`
    const timestamp = now()
    const prior = [...this.jobs.values()]
      .filter(job => job.visual_plan_id === plan.id && job.best?.asset_id)
      .sort((left, right) => String(right.updated_at).localeCompare(String(left.updated_at)))[0]
    const job = {
      id,
      visual_plan_id: plan.id,
      status: 'queued',
      attempts: 0,
      maximum_attempts: this.maxAttempts,
      generation: planJobs.length + 1,
      maximum_generations: this.maxJobsPerPlan,
      stagnation_count: 0,
      strategy: 'surgical',
      best: prior ? safeSnapshot(prior.best) : null,
      locked_constraints: prior ? safeSnapshot(prior.locked_constraints) : {
          preflight_passed: false,
          labels: [],
          scientific_checks: [],
          design_checks: [],
        },
      seen_source_sha256: prior ? [...(prior.seen_source_sha256 ?? [])] : [],
      failure_signatures: {},
      last_feedback: prior ? uniqueText([
        ...(prior.best?.actionable_feedback ?? prior.last_feedback ?? []),
        `Continue from retained champion ${prior.best.asset_id}; do not recreate the SVG from scratch.`,
      ]) : [],
      last_worker_thread_id: null,
      created_at: timestamp,
      updated_at: timestamp,
    }
    this.jobs.set(id, job)
    await this.#persist()
    this.#schedulePump()
    return { delegated: true, job: publicJob(job) }
  }

  status(jobId = '') {
    if (jobId) {
      const job = this.jobs.get(jobId)
      if (!job) throw new Error(`unknown svg job: ${jobId}`)
      return { job: publicJob(job) }
    }
    return { jobs: [...this.jobs.values()].map(publicJob) }
  }

  async collect(jobId) {
    const job = this.jobs.get(jobId)
    if (!job) throw new Error(`unknown svg job: ${jobId}`)
    if (job.status !== 'passed') {
      return { ready: false, job: publicJob(job) }
    }
    const asset = await this.readRegisteredAsset(this.workspace, job.best.asset_id)
    return {
      ready: true,
      job: publicJob(job),
      asset: {
        id: asset.entry.id,
        path: asset.entry.path,
        sha256: asset.sha256,
        caption: asset.entry.caption,
        alt_text: asset.entry.alt_text,
        visual_plan_id: asset.entry.visual_plan_id,
      },
    }
  }

  async wait(jobId = '', timeoutMs = 15_000) {
    if (jobId && !this.jobs.has(jobId)) throw new Error(`unknown svg job: ${jobId}`)
    const before = this.version
    const terminal = jobId
      ? TERMINAL_STATUSES.has(this.jobs.get(jobId).status)
      : ![...this.jobs.values()].some(job => ACTIVE_STATUSES.has(job.status))
    if (terminal) return { changed: false, timed_out: false, ...this.status(jobId) }
    const bounded = boundedInteger(timeoutMs, 15_000, 250, 30_000, 'svg wait timeoutMs')
    await new Promise(resolve => {
      const waiter = { resolve, timer: null }
      waiter.timer = setTimeout(() => {
        this.waiters.delete(waiter)
        resolve()
      }, bounded)
      this.waiters.add(waiter)
    })
    return { changed: this.version !== before, timed_out: this.version === before, ...this.status(jobId) }
  }

  async stop() {
    this.stopping = true
    for (const job of this.jobs.values()) {
      if (!ACTIVE_STATUSES.has(job.status)) continue
      job.status = 'queued'
      job.updated_at = now()
    }
    await this.#persist()
    this.#notifyWaiters()
  }

  async settle() {
    await Promise.allSettled([...this.activeRuns])
  }

  #schedulePump() {
    queueMicrotask(() => {
      void this.#pump().catch(async error => {
        await this.recorder?.record('host_notice', { kind: 'svg_job_pump_failed', message: error.message })
      })
    })
  }

  async #pump() {
    if (this.stopping) return
    while (this.activeCount < this.maxConcurrent) {
      const job = [...this.jobs.values()].find(item => item.status === 'queued')
      if (!job) return
      this.activeCount += 1
      job.status = job.attempts === 0 ? 'running' : 'revising'
      job.updated_at = now()
      await this.#persist()
      const run = this.#runJob(job).catch(async error => {
        await this.recorder?.record('host_notice', { kind: 'svg_job_run_failed', job_id: job.id, message: error.message })
      })
      this.activeRuns.add(run)
      void run.finally(() => {
        this.activeRuns.delete(run)
        this.activeCount -= 1
        if (!this.stopping) this.#schedulePump()
      })
    }
  }

  async #runJob(job) {
    try {
      const plan = await resolveVisualPlan(this.workspace, job.visual_plan_id)
      while (!this.stopping && job.attempts < job.maximum_attempts) {
        job.attempts += 1
        job.status = job.attempts === 1 ? 'running' : 'revising'
        job.updated_at = now()
        let workerThreadId = null
        try {
          const baseline = await this.#baseline(job)
          const prompt = this.#workerPrompt(job, plan, baseline)
          workerThreadId = await this.startWorker({ job: publicJob(job), plan, baseline })
          job.last_worker_thread_id = workerThreadId
          await this.#persist()
          const candidate = await this.runWorker({
            threadId: workerThreadId,
            prompt,
            outputSchema: baseline ? SVG_WORKER_REVISION_OUTPUT_SCHEMA : SVG_WORKER_OUTPUT_SCHEMA,
            job: publicJob(job),
            plan,
            baseline,
          })
          const normalized = {
            svg: normalizedText(candidate.svg, 'svg worker output.svg', 500_000),
            caption: normalizedText(candidate.caption, 'svg worker output.caption', 2_000),
            alt_text: normalizedText(candidate.alt_text, 'svg worker output.alt_text', 2_000),
            change_summary: normalizedText(candidate.change_summary, 'svg worker output.change_summary', 2_000),
          }
          const sha256 = sourceSha256(normalized.svg)
          if (job.seen_source_sha256.includes(sha256)) {
            await this.#recordNoProgress(job, [`duplicate SVG source returned: ${sha256}`])
            continue
          }
          job.seen_source_sha256.push(sha256)
          const evaluation = await this.processCandidate({ job: publicJob(job), plan, candidate: normalized, source_sha256: sha256 })
          const fitness = candidateFitness(evaluation)
          const regressions = lockRegressions(job.locked_constraints, evaluation)
          const improves = regressions.length === 0 && compareFitness(fitness, job.best?.fitness) > 0
          const challengerFeedback = uniqueText([
            ...regressions,
            ...feedbackFromEvaluation(evaluation),
          ])
          if (improves && evaluation.asset_id) {
            const candidateLocks = locksFromEvaluation(evaluation)
            job.best = {
              asset_id: evaluation.asset_id,
              asset_path: evaluation.asset_path,
              asset_sha256: evaluation.asset_sha256,
              source_sha256: sha256,
              fitness,
              preflight_id: evaluation.preflight?.preflight_id ?? null,
              review_id: reviewReceipt(evaluation)?.id ?? null,
              diagnostic_verdict: diagnosticReview(evaluation)?.verdict ?? null,
              diagnostic_summary: diagnosticReview(evaluation)?.summary ?? null,
              actionable_feedback: challengerFeedback,
            }
            job.locked_constraints = mergeLocks(job.locked_constraints, candidateLocks)
            job.stagnation_count = 0
            job.strategy = 'surgical'
          } else {
            job.stagnation_count += 1
          }
          job.last_feedback = improves
            ? challengerFeedback
            : uniqueText(job.best?.actionable_feedback ?? challengerFeedback)
          const signature = failureSignature(challengerFeedback)
          job.failure_signatures[signature] = (job.failure_signatures[signature] ?? 0) + 1
          if ((job.best?.fitness?.issue_count ?? Number.POSITIVE_INFINITY) > 4
            && (job.stagnation_count >= this.stagnationLimit || job.failure_signatures[signature] >= this.stagnationLimit)) {
            job.strategy = 'layout_reset'
          }
          if (reviewReceipt(evaluation)?.verdict === 'pass' && regressions.length === 0) {
            job.status = 'passed'
            job.updated_at = now()
            await this.#persist()
            return
          }
          job.updated_at = now()
          await this.#persist()
        } catch (error) {
          if (this.stopping) return
          await this.#recordNoProgress(job, [error.message])
        } finally {
          if (workerThreadId) await this.disposeWorker(workerThreadId).catch(() => {})
        }
      }
      if (!this.stopping) {
        job.status = 'failed'
        job.updated_at = now()
        job.last_feedback = uniqueText([
          ...(job.last_feedback ?? []),
          `SVG job exhausted its bounded ${job.maximum_attempts}-attempt budget without a passing independent review.`,
        ])
        await this.#persist()
      }
    } catch (error) {
      if (this.stopping) return
      job.status = 'failed'
      job.updated_at = now()
      job.last_feedback = uniqueText([...(job.last_feedback ?? []), error.message])
      await this.#persist()
    }
  }

  async #recordNoProgress(job, feedback) {
    job.stagnation_count += 1
    job.last_feedback = uniqueText(feedback)
    const signature = failureSignature(job.last_feedback)
    job.failure_signatures[signature] = (job.failure_signatures[signature] ?? 0) + 1
    if ((job.best?.fitness?.issue_count ?? Number.POSITIVE_INFINITY) > 4
      && (job.stagnation_count >= this.stagnationLimit || job.failure_signatures[signature] >= this.stagnationLimit)) {
      job.strategy = 'layout_reset'
    }
    job.updated_at = now()
    await this.#persist()
  }

  async #baseline(job) {
    if (!job.best?.asset_id) return null
    const asset = await this.readRegisteredAsset(this.workspace, job.best.asset_id)
    return {
      asset_id: asset.entry.id,
      source: Buffer.from(asset.bytes).toString('utf8'),
      caption: asset.entry.caption,
      alt_text: asset.entry.alt_text,
    }
  }

  #workerPrompt(job, plan, baseline) {
    const strategy = job.strategy === 'layout_reset'
      ? 'Recompose the existing id-addressed groups on a simpler grid with shorter connectors and more whitespace. Keep the locked scientific topology, labels, and stable ids.'
      : 'Make a focused, coherent edit that resolves the current findings while retaining the champion structure that already works.'
    return [
      baseline
        ? 'Revise the champion like code through svg_edit calls against stable element ids. Prefer one atomic operations batch for coordinated fixes. Make at least one accepted edit and return metadata plus the final edit revision, without SVG source.'
        : 'Create the initial complete standalone publication SVG and return it in the requested JSON object. Give every meaningful group, connector, shape, and text element a stable unique id for later tool edits.',
      `Visual plan: ${JSON.stringify(plan)}`,
      `Attempt: ${job.attempts}/${job.maximum_attempts}. Strategy: ${job.strategy}.`,
      `Locked pass ledger: ${JSON.stringify(job.locked_constraints)}. Keep every listed pass visibly true.`,
      `Current actionable findings: ${JSON.stringify(job.last_feedback ?? [])}.`,
      'Resolve deterministic findings in their listed order; their text_id, shape_id, left_id, and right_id fields name the exact editable targets. Treat pixel-review findings as secondary visual guidance. Do not disturb unrelated regions that already work.',
      strategy,
      'Use exact required-label text. Keep the SVG self-contained, safe, under 60,000 characters, and readable at the planned publication width. Use a restrained semantic palette with non-colour cues, route connectors around text, and keep all text at least 8 pt at final width.',
      'Every required label must be visibly painted. Never satisfy a label with opacity=0, display=none, visibility=hidden, off-canvas text, or a concealed duplicate. For fragile mathematical superscripts/subscripts, compose visible ordinary glyphs with baseline-shift tspans and place the exact canonical formula in aria-label on that same visible text element; the visible text must be typographically equivalent. Split mixed-script runs into visible tspans when needed for reliable font fallback.',
      'For text_below_minimum_font_size current<minimum findings, the value after < is the required SVG-unit font size. Resolve crowding through layout, sizing, concise labels, and clear routing rather than smaller text.',
      baseline
        ? 'After the coherent svg_edit batch, call svg_preflight_draft on the host-held draft. If it passes, deliver immediately. If it fails, use the returned ids for one more focused batch and recheck; do not reproduce preflight logic in shell.'
        : 'Before delivery, call svg_preflight_candidate on the exact complete SVG. If it passes, deliver immediately. If it fails, repair that same candidate using the returned ids and recheck; do not restart the drawing or reproduce preflight logic in shell.',
      baseline
        ? `Champion baseline asset ${baseline.asset_id}. This exact source is loaded into svg_edit. Inspect its stable ids and modify the relevant elements:\n<svg_baseline>\n${baseline.source}\n</svg_baseline>`
        : 'There is no accepted baseline yet. Build a simple explicit topology on a regular grid before adding decoration.',
    ].join('\n\n')
  }

  async #processCandidate({ job, plan, candidate, source_sha256: sha256 }) {
    const manifest = await this.readAssetManifest(this.workspace)
    const predecessor = currentVisualAsset(manifest, plan.id)
    const assetId = `svg-${job.id.slice(-8)}-${String(job.attempts).padStart(2, '0')}-${sha256.slice(0, 12)}`
    const submission = await submitSvg(this.workspace, {
      id: assetId,
      svg: candidate.svg,
      caption: candidate.caption,
      alt_text: candidate.alt_text,
      visual_plan_id: plan.id,
      used_in: [plan.section_id],
      source: 'agent',
      provenance: `agent_generated:svg-worker:${job.id}`,
      licence: 'generated_internal',
      ...(predecessor ? { supersedes_asset_id: predecessor.id } : {}),
    }, {
      registerAsset,
      resolveVisualPlan,
    })
    if (!submission.registered) return { submission }
    const preflight = await preflightAsset(this.workspace, { asset_id: submission.asset_id }, {
      registerAsset,
      readRegisteredAsset,
      readAssetManifest,
      resolveVisualPlan,
      appendVisualPreflight,
    })
    if (preflight.status !== 'passed') {
      let diagnostic = null
      if (typeof this.diagnoseVisual === 'function') {
        try {
          diagnostic = await this.diagnoseVisual({
            asset_id: submission.asset_id,
            preflight_id: preflight.preflight_id,
          })
        } catch (error) {
          diagnostic = { status: 'diagnostic_error', error: error.message }
          await this.recorder?.record('host_notice', {
            kind: 'svg_visual_diagnostic_failed',
            job_id: job.id,
            asset_id: submission.asset_id,
            preflight_id: preflight.preflight_id,
            message: error.message,
          })
        }
      }
      return {
        submission,
        preflight,
        diagnostic,
        asset_id: submission.asset_id,
        asset_path: submission.asset_path,
        asset_sha256: submission.asset_sha256,
      }
    }
    const review = await this.inspectVisual({ asset_id: submission.asset_id, preflight_id: preflight.preflight_id })
    return {
      submission,
      preflight,
      review,
      asset_id: submission.asset_id,
      asset_path: submission.asset_path,
      asset_sha256: submission.asset_sha256,
    }
  }

  async #persist() {
    const snapshot = Object.fromEntries([...this.jobs].map(([id, job]) => [id, safeSnapshot(job)]))
    if (this.recorder) await this.recorder.update({ svg_jobs: snapshot })
    this.version += 1
    this.#notifyWaiters()
  }

  #notifyWaiters() {
    for (const waiter of this.waiters) {
      clearTimeout(waiter.timer)
      waiter.resolve()
    }
    this.waiters.clear()
  }
}
