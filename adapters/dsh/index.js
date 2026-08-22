import { defineTool } from '@deepseek-ai/dsh-tools'

import {
  PublicationKernel,
  REVIEW_OUTPUT_SCHEMA,
  executeAndRecordReview,
  readProject,
} from '@longwriter/core'

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
import { applySvg } from './svg/index.js'

export const name = 'longwriter-native'
export const inject = ['tools', 'systemPrompt', 'goals', 'subagents']

const REVIEW_TOOLS = Object.freeze([
  'read',
  'read_image',
  'grep',
  'glob',
  'web_search',
  'publication_status',
])

const POLICY = `
You are the root publication agent using the optional LongWriter DSH adapter.

LongWriter Core owns the canonical publication files, shared revision, atomic mutations, deterministic validation, review receipts, and finalization gate. DSH owns only conversation history, compaction, automatic Goal rounds, and child-agent execution.

Start with initialize_publication. Before every mutation, inspect publication_status and pass its revision as expected_revision. Advance one coherent unit per automatic Goal round. Use commit_chunk or revise_chunk rather than generic file writes. A revision conflict means another client changed the publication; reread status and reconsider the edit instead of retrying blindly.

Before drawing a figure, call plan_visuals. For SVG, call svg_check, svg_submit, svg_preflight, inspect the retained PNG with read_image, then call svg_record_review. Never hand-edit assets/manifest.json or fabricate evidence.

Near completion call review_publication. The adapter runs a fresh read-only child session and records trusted execution evidence; the reviewer model cannot attest its own isolation. Only finalize_publication may certify the publication and complete the DSH Goal.

Preserve uncertainty. Never invent citations, provenance, licences, quantitative results, or reviewer evidence. Read relevant earlier sections before writing so terminology and argument structure remain globally coherent.
`.trim()

const REVIEWER_PERSONA = `
You are an independent adversarial publication reviewer. You did not author the manuscript and receive no parent conversation transcript. Inspect project.json, article.md, assets/manifest.json, and every required retained visual preview directly with read-only tools. Judge factual discipline, objective coverage, cross-section coherence, unsupported claims, terminology, evidence handling, citation hygiene, visual readability, and asset provenance. Do not modify files. Return only the required structured review bound to the exact article SHA in the request.
`.trim()

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

function registerJsonTool(ctx, definition) {
  ctx.tools.register(defineTool({ ...definition, output: JSON_OUTPUT }))
}

function kernelFromExecution(exec) {
  return new PublicationKernel(workspaceFromExecution(exec), { signal: exec.signal })
}

async function executeIndependentReview(ctx, exec, kernel, focus = '') {
  return executeAndRecordReview(kernel, {
    id: 'dsh-subagent-runtime',
    async execute(request) {
      const startedAt = new Date().toISOString()
      const review = await runFreshReviewer(ctx, exec, {
        prompt: request.prompt,
        outputSchema: REVIEW_OUTPUT_SCHEMA,
        toolAllowlist: REVIEW_TOOLS,
        persona: REVIEWER_PERSONA,
      })
      const execution = kernel.createExecutionEvidence('dsh-subagent', {
        isolation: 'fresh_context',
        tool_allowlist: REVIEW_TOOLS,
        started_at: startedAt,
        completed_at: new Date().toISOString(),
      })
      return { review, execution }
    },
  }, { focus })
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
    return 'Generic filesystem mutation is disabled in the LongWriter profile; use publication domain tools.'
  })

  registerJsonTool(ctx, {
    name: 'initialize_publication',
    description: 'Initialize LongWriter Core state and create or re-arm the durable DSH publication Goal.',
    parameters: {
      project: { type: 'json', required: true, description: 'Complete publication project object.' },
      max_goal_rounds: { type: 'number', description: 'Maximum automatic DSH Goal rounds; default 256.' },
    },
    async execute(args, exec) {
      const initialized = await kernelFromExecution(exec).initialize(args.project)
      const rounds = positiveInteger(args.max_goal_rounds, 'max_goal_rounds', 256)
      const goal = ensurePublicationGoal(ctx, requireAgent(exec), initialized.project.objective, rounds)
      exec.concludeTurn()
      return {
        ...initialized,
        goal: {
          id: goal.id,
          revision: goal.revision,
          phase: goal.phase,
          activation: goal.activation,
          max_goal_rounds: goal.maxGoalRounds,
        },
        dsh_compatibility: DSH_COMPATIBILITY,
      }
    },
  })

  registerJsonTool(ctx, {
    name: 'plan_visuals',
    description: 'Atomically replace project.json.visual_contract through LongWriter Core.',
    parameters: {
      visual_contract: { type: 'json', required: true },
      expected_revision: { type: 'number' },
    },
    async execute(args, exec) {
      const result = await kernelFromExecution(exec).planVisuals(args.visual_contract, {
        expectedRevision: args.expected_revision,
      })
      exec.concludeTurn()
      return result
    },
  })

  registerJsonTool(ctx, {
    name: 'resume_publication',
    description: 'Re-arm the DSH Goal after reopening a persisted Session; publication state remains owned by Core.',
    parameters: {},
    async execute(_args, exec) {
      const project = await readProject(workspaceFromExecution(exec))
      const goal = resumePublicationGoal(ctx, requireAgent(exec))
      if (goal.objective !== project.objective) {
        throw new Error('the resumed DSH goal does not match project.json')
      }
      const status = await kernelFromExecution(exec).status()
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
        status,
      }
    },
  })

  registerJsonTool(ctx, {
    name: 'publication_status',
    description: 'Read deterministic manuscript progress, article hash, shared revision, and finalization state.',
    parameters: {},
    execute(_args, exec) {
      return kernelFromExecution(exec).status()
    },
  })

  registerJsonTool(ctx, {
    name: 'commit_chunk',
    description: 'Atomically append one coherent Markdown chunk through LongWriter Core.',
    parameters: {
      section_id: { type: 'string', required: true },
      chunk_id: { type: 'string', required: true },
      markdown: { type: 'string', required: true },
      expected_revision: { type: 'number' },
    },
    async execute(args, exec) {
      const result = await kernelFromExecution(exec).commitChunk(args, {
        expectedRevision: args.expected_revision,
      })
      exec.concludeTurn()
      return result
    },
  })

  registerJsonTool(ctx, {
    name: 'revise_chunk',
    description: 'Atomically replace one existing chunk through LongWriter Core.',
    parameters: {
      chunk_id: { type: 'string', required: true },
      markdown: { type: 'string', required: true },
      expected_revision: { type: 'number' },
    },
    async execute(args, exec) {
      const result = await kernelFromExecution(exec).reviseChunk(args, {
        expectedRevision: args.expected_revision,
      })
      exec.concludeTurn()
      return result
    },
  })

  registerJsonTool(ctx, {
    name: 'review_publication',
    description: 'Run a fresh read-only DSH reviewer and record a Core-validated execution receipt.',
    parameters: {
      focus: { type: 'string' },
    },
    async execute(args, exec) {
      const kernel = kernelFromExecution(exec)
      const validator = await kernel.validate()
      const review = await executeIndependentReview(ctx, exec, kernel, args.focus ?? '')
      exec.concludeTurn()
      return { validator, ...review }
    },
  })

  registerJsonTool(ctx, {
    name: 'finalize_publication',
    description: 'Validate, run and record a fresh independent review, then finalize Core and complete the DSH Goal.',
    parameters: {},
    async execute(_args, exec) {
      const kernel = kernelFromExecution(exec)
      const status = await kernel.status()
      if (status.finalized) {
        const goal = completePublicationGoal(ctx, requireAgent(exec))
        exec.concludeTurn()
        return {
          finalized: true,
          already_finalized: true,
          article_sha256: status.article_sha256,
          revision: status.revision,
          goal: {
            id: goal.id,
            revision: goal.revision,
            phase: goal.phase,
            rounds_started: goal.roundsStarted,
          },
        }
      }
      const validator = await kernel.validate()
      if (!validator.validator.passed) {
        exec.concludeTurn()
        return {
          finalized: false,
          reason: 'deterministic_validation_failed',
          ...validator,
        }
      }

      const review = await executeIndependentReview(ctx, exec, kernel)
      const finalized = await kernel.finalize({ expectedRevision: review.recorded.revision })
      if (!finalized.finalized) {
        exec.concludeTurn()
        return { ...finalized, review }
      }

      const goal = completePublicationGoal(ctx, requireAgent(exec))
      exec.concludeTurn()
      return {
        ...finalized,
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

  applySvg(definition => registerJsonTool(ctx, definition), kernelFromExecution)
}
