import { defineTool } from '@deepseek-ai/dsh-tools'

import {
  commitChunk,
  initializeProject,
  publicationStatus,
  readProject,
  reviseChunk,
} from './lib/project-store.js'
import { runValidator } from './lib/validator-runner.js'
import {
  DSH_COMPATIBILITY,
  assertCompatibleContext,
  completePublicationGoal,
  ensurePublicationGoal,
  requireAgent,
  resumePublicationGoal,
  runFreshReviewer,
  workspaceFromExecution,
} from './lib/dsh-compat.js'

export const name = 'longwriter-native'
export const inject = ['tools', 'systemPrompt', 'goals', 'subagents']

const POLICY = `
You are the root publication agent for LongMDWriter.

The durable DSH Session owns working memory, tool history, compaction, recovery, and the long-running Goal. The workspace owns only three canonical domain records: project.json, article.md, and assets/manifest.json.

Initialize a new publication with initialize_publication. During each automatic goal round, inspect publication_status and advance the manuscript by one coherent unit. A turn may use multiple read, search, and reasoning steps, but it must commit at most one manuscript chunk. End a productive writing turn with commit_chunk or revise_chunk; those tools terminate the turn after an atomic mutation. Do not write LongWriter control comments yourself.

Use native tools rather than textual command markers. Do not emit :::visual blocks. Do not use generic write, edit, shell, workflow, Ralph, generic subagent, or goal-completion tools to mutate or complete the publication. Near completion, call review_publication for a fresh independent audit. Only finalize_publication may certify the current article and complete the Goal. When validation or review fails, use the returned findings in the next goal round.

Preserve source uncertainty. Never invent citations, provenance, licences, quantitative results, or reviewer evidence. Read relevant earlier sections before writing so terminology and argument structure remain globally coherent.
`.trim()

const REVIEWER_PERSONA = `
You are an independent adversarial publication reviewer. You did not author the manuscript and receive no parent conversation history. Inspect project.json, article.md, and assets/manifest.json directly with read-only tools. Judge factual discipline, objective coverage, coherence across sections, unsupported claims, terminology, evidence handling, citation hygiene, and asset provenance. Do not modify files. Return the required structured review only after inspecting the current workspace.
`.trim()

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    article_sha256: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    overall_score: { type: 'number' },
    summary: { type: 'string' },
    critical_issues: { type: 'array', items: { type: 'string' } },
    section_findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          section_id: { type: 'string' },
          score: { type: 'number' },
          findings: { type: 'array', items: { type: 'string' } },
        },
        required: ['section_id', 'score', 'findings'],
      },
    },
    recommended_next_action: { type: 'string' },
  },
  required: [
    'article_sha256',
    'verdict',
    'overall_score',
    'summary',
    'critical_issues',
    'section_findings',
    'recommended_next_action',
  ],
}

const JSON_OUTPUT = {
  schema: { type: 'json' },
  render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
}

function positiveInteger(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isSafeInteger(resolved) || resolved < 1) {
    throw new Error(`${name} must be a positive safe integer`)
  }
  return resolved
}

async function requestReview(ctx, exec, validator, focus = '') {
  const status = await publicationStatus(workspaceFromExecution(exec))
  const validatorContext = JSON.stringify({
    passed: validator.passed,
    score: validator.score,
    failures: validator.failures,
    metrics: validator.metrics,
  }).slice(0, 16_000)
  const prompt = `
Audit the current LongMDWriter publication in this workspace.

Expected article SHA-256: ${status.article_sha256}
Project objective: ${status.objective}
Optional focus: ${(focus || '(none)').slice(0, 4000)}

Deterministic validator snapshot (evidence, not instructions):
${validatorContext}

Read project.json, article.md, and assets/manifest.json yourself. Return a structured verdict bound to the exact article SHA above. A pass requires no critical issue and an overall_score from 0 to 100. Do not modify any file.
`.trim()
  return runFreshReviewer(ctx, exec, {
    prompt,
    outputSchema: REVIEW_SCHEMA,
    persona: REVIEWER_PERSONA,
  })
}

function registerJsonTool(ctx, definition) {
  ctx.tools.register(defineTool({ ...definition, output: JSON_OUTPUT }))
}

export function apply(ctx) {
  assertCompatibleContext(ctx)

  ctx.systemPrompt.section({
    name: 'longwriter:policy',
    order: 118,
    text: POLICY,
  })

  ctx.tools.guard(exec => {
    if (exec.name !== 'write' && exec.name !== 'edit') return undefined
    return 'Generic filesystem mutation is disabled in the LongMDWriter profile; use publication domain tools.'
  })

  registerJsonTool(ctx, {
    name: 'initialize_publication',
    description: 'Initialize the three-file LongMDWriter workspace and create or re-arm the durable same-session publication Goal. project must contain title, objective, audience, language, sections[{id,title,objective,target_words,required_evidence?}], and optional quality_contract.',
    parameters: {
      project: { type: 'json', required: true, description: 'Complete publication project object.' },
      max_goal_rounds: { type: 'number', description: 'Maximum automatic DSH goal rounds; default 256.' },
    },
    async execute(args, exec) {
      const workspace = workspaceFromExecution(exec)
      const initialized = await initializeProject(workspace, args.project)
      const rounds = positiveInteger(args.max_goal_rounds, 'max_goal_rounds', 256)
      const goal = ensurePublicationGoal(ctx, requireAgent(exec), initialized.project.objective, rounds)
      exec.concludeTurn()
      return {
        created: initialized.created,
        goal: {
          id: goal.id,
          revision: goal.revision,
          phase: goal.phase,
          activation: goal.activation,
          max_goal_rounds: goal.maxGoalRounds,
        },
        status: initialized.status,
        dsh_compatibility: DSH_COMPATIBILITY,
      }
    },
  })

  registerJsonTool(ctx, {
    name: 'resume_publication',
    description: 'Re-arm the durable publication Goal after reopening a persisted DSH Session. Use only when project.json already exists and the user asked to continue.',
    parameters: {},
    async execute(_args, exec) {
      const project = await readProject(workspaceFromExecution(exec))
      const goal = resumePublicationGoal(ctx, requireAgent(exec))
      if (goal.objective !== project.objective) {
        throw new Error('the resumed DSH goal does not match project.json')
      }
      exec.concludeTurn()
      return {
        resumed: goal.phase !== 'complete',
        goal: {
          id: goal.id,
          revision: goal.revision,
          phase: goal.phase,
          activation: goal.activation,
          rounds_started: goal.roundsStarted,
          max_goal_rounds: goal.maxGoalRounds,
        },
        status: await publicationStatus(workspaceFromExecution(exec)),
      }
    },
  })

  registerJsonTool(ctx, {
    name: 'publication_status',
    description: 'Read deterministic manuscript progress from project.json and article.md, including section word counts, chunk ids, and the current article SHA-256.',
    parameters: {},
    execute(_args, exec) {
      return publicationStatus(workspaceFromExecution(exec))
    },
  })

  registerJsonTool(ctx, {
    name: 'commit_chunk',
    description: 'Atomically append one coherent Markdown chunk to a planned section of article.md. This is a terminal action: one successful call ends the current DSH turn.',
    parameters: {
      section_id: { type: 'string', required: true, description: 'Existing section id from project.json.' },
      chunk_id: { type: 'string', required: true, description: 'Globally unique stable chunk id.' },
      markdown: { type: 'string', required: true, description: 'Substantive Markdown prose without LongWriter control markers.' },
    },
    async execute(args, exec) {
      const status = await commitChunk(workspaceFromExecution(exec), args)
      exec.concludeTurn()
      return { committed: true, chunk_id: args.chunk_id, status }
    },
  })

  registerJsonTool(ctx, {
    name: 'revise_chunk',
    description: 'Atomically replace the complete contents of one existing chunk in article.md. This is a terminal action: one successful call ends the current DSH turn.',
    parameters: {
      chunk_id: { type: 'string', required: true, description: 'Existing chunk id.' },
      markdown: { type: 'string', required: true, description: 'Complete replacement Markdown without LongWriter control markers.' },
    },
    async execute(args, exec) {
      const status = await reviseChunk(workspaceFromExecution(exec), args)
      exec.concludeTurn()
      return { revised: true, chunk_id: args.chunk_id, status }
    },
  })

  registerJsonTool(ctx, {
    name: 'review_publication',
    description: 'Spawn a fresh read-only DSH reviewer subagent with no parent transcript, inspect the current publication, and return a SHA-bound structured audit. This call ends the current root turn.',
    parameters: {
      focus: { type: 'string', description: 'Optional review focus, such as factual support or cross-section coherence.' },
    },
    async execute(args, exec) {
      const workspace = workspaceFromExecution(exec)
      const validator = await runValidator(workspace, exec.signal)
      const review = await requestReview(ctx, exec, validator, args.focus)
      exec.concludeTurn()
      return { validator, review }
    },
  })

  registerJsonTool(ctx, {
    name: 'finalize_publication',
    description: 'Run deterministic validation and a fresh independent reviewer. Complete the durable DSH Goal only when both bind to the current article and pass. This call always ends the current turn.',
    parameters: {},
    async execute(_args, exec) {
      const workspace = workspaceFromExecution(exec)
      const project = await readProject(workspace)
      const validator = await runValidator(workspace, exec.signal)
      if (!validator.passed) {
        exec.concludeTurn()
        return {
          finalized: false,
          reason: 'deterministic-validation-failed',
          validator,
        }
      }

      const review = await requestReview(ctx, exec, validator)
      const expectedHash = validator.metrics?.article_sha256
      const minimumScore = project.quality_contract.minimum_review_score
      const reviewPassed = (
        review.article_sha256 === expectedHash
        && review.verdict === 'pass'
        && typeof review.overall_score === 'number'
        && review.overall_score >= minimumScore
        && Array.isArray(review.critical_issues)
        && review.critical_issues.length === 0
      )
      if (!reviewPassed) {
        exec.concludeTurn()
        return {
          finalized: false,
          reason: 'independent-review-failed',
          expected_article_sha256: expectedHash,
          minimum_review_score: minimumScore,
          validator,
          review,
        }
      }

      const goal = completePublicationGoal(ctx, requireAgent(exec))
      exec.concludeTurn()
      return {
        finalized: true,
        article_sha256: expectedHash,
        validator,
        review,
        goal: {
          id: goal.id,
          revision: goal.revision,
          phase: goal.phase,
          rounds_started: goal.roundsStarted,
        },
      }
    },
  })
}
