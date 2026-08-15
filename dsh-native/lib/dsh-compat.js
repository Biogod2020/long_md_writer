import path from 'node:path'

export const DSH_COMPATIBILITY = Object.freeze({
  cliVersion: '0.1.0-rc.6',
  toolsPackageVersion: '0.1.0-rc.6',
  sourceContractCommit: '47f943859bef60e4160492346772ded9b24f765a',
  sessionStoreNamespace: 'dsh-0.1.0-rc.6',
})

function requireFunction(owner, name, label) {
  if (owner === undefined || owner === null || typeof owner[name] !== 'function') {
    throw new Error(
      `DSH compatibility check failed: ${label}.${name} is unavailable; `
      + `this plugin targets CLI ${DSH_COMPATIBILITY.cliVersion}, `
      + `dsh-tools ${DSH_COMPATIBILITY.toolsPackageVersion}, and the public seam `
      + `contract inspected at ${DSH_COMPATIBILITY.sourceContractCommit}`,
    )
  }
  return owner[name].bind(owner)
}

export function assertCompatibleContext(ctx) {
  requireFunction(ctx?.tools, 'register', 'ctx.tools')
  requireFunction(ctx?.tools, 'guard', 'ctx.tools')
  requireFunction(ctx?.systemPrompt, 'section', 'ctx.systemPrompt')
  requireFunction(ctx?.goals, 'get', 'ctx.goals')
  requireFunction(ctx?.goals, 'create', 'ctx.goals')
  requireFunction(ctx?.goals, 'resume', 'ctx.goals')
  requireFunction(ctx?.goals, 'complete', 'ctx.goals')
  requireFunction(ctx?.subagents, 'start', 'ctx.subagents')
}

export function requireAgent(exec) {
  if (!exec?.agent) throw new Error('longwriter tools require an active DSH Agent')
  return exec.agent
}

export function workspaceFromExecution(exec) {
  const agent = requireAgent(exec)
  const cwd = agent.session?.header?.cwd
  if (typeof cwd !== 'string' || cwd.length === 0 || !path.isAbsolute(cwd)) {
    throw new Error('the active DSH Session must have an absolute workspace cwd')
  }
  return path.resolve(cwd)
}

function ref(goal) {
  return { id: goal.id, revision: goal.revision }
}

export function ensurePublicationGoal(ctx, agent, objective, maxGoalRounds = 256) {
  const existing = ctx.goals.get(agent)
  if (existing === undefined) {
    return ctx.goals.create(agent, { objective, maxGoalRounds })
  }
  if (existing.phase === 'complete') {
    throw new Error('this DSH Session already contains a completed goal; start the next publication in a new Session')
  }
  if (existing.objective !== objective) {
    throw new Error('the active DSH goal does not match project.json; use a new Session instead of replacing history')
  }
  if (existing.phase !== 'active' || existing.activation !== 'armed') {
    return ctx.goals.resume(agent, ref(existing))
  }
  return existing
}

export function resumePublicationGoal(ctx, agent) {
  const goal = ctx.goals.get(agent)
  if (goal === undefined) throw new Error('no publication goal exists in this Session')
  if (goal.phase === 'complete') return goal
  if (goal.phase === 'active' && goal.activation === 'armed') return goal
  return ctx.goals.resume(agent, ref(goal))
}

export function completePublicationGoal(ctx, agent) {
  const goal = ctx.goals.get(agent)
  if (goal === undefined) throw new Error('no publication goal exists in this Session')
  if (goal.phase === 'complete') return goal
  return ctx.goals.complete(agent, ref(goal))
}

export async function runFreshReviewer(ctx, exec, request) {
  const agent = requireAgent(exec)
  const run = await ctx.subagents.start('spawn', {
    label: 'publication-reviewer',
    prompt: [{ type: 'text', text: request.prompt }],
    parent: agent,
    signal: exec.signal,
    outputSchema: request.outputSchema,
    maxDepth: 1,
    toolFilter: {
      allow: ['read', 'read_image', 'grep', 'glob', 'web_search', 'publication_status'],
    },
    persona: request.persona,
  })
  try {
    const result = await run.result
    if (result.stopReason !== 'completed') {
      const partial = Array.isArray(result.output)
        ? result.output.filter(block => block?.type === 'text').map(block => block.text).join('')
        : ''
      throw new Error(`reviewer stopped with ${result.stopReason}${partial ? `: ${partial.slice(0, 2000)}` : ''}`)
    }
    if (result.structured === undefined || result.structured === null || typeof result.structured !== 'object') {
      throw new Error('reviewer completed without the required structured result')
    }
    return result.structured
  } finally {
    await run.dispose()
  }
}
