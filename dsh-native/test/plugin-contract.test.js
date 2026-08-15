import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { apply } from '../index.js'

function fakeContext(workspace) {
  const tools = new Map()
  let guard
  let goal
  const ctx = {
    tools: {
      register(definition) { tools.set(definition.name, definition) },
      guard(value) { guard = value },
    },
    systemPrompt: { section() {} },
    goals: {
      get() { return goal },
      create(_agent, input) {
        goal = {
          id: 'goal-1', revision: 1, objective: input.objective,
          phase: 'active', activation: 'armed', roundsStarted: 0,
          maxGoalRounds: input.maxGoalRounds,
        }
        return goal
      },
      resume() {
        goal = { ...goal, revision: goal.revision + 1, phase: 'active', activation: 'armed' }
        return goal
      },
      complete() {
        goal = { ...goal, revision: goal.revision + 1, phase: 'complete', activation: 'disarmed' }
        return goal
      },
    },
    subagents: {
      async start(_provider, request) {
        const sha = request.prompt[0].text.match(/Expected article SHA-256: ([a-f0-9]{64})/)?.[1]
        return {
          result: Promise.resolve({
            stopReason: 'completed',
            output: [],
            structured: {
              article_sha256: sha,
              verdict: 'pass',
              overall_score: 95,
              summary: 'The current article satisfies the review contract.',
              critical_issues: [],
              section_findings: [{ section_id: 'intro', score: 95, findings: [] }],
              recommended_next_action: 'finalize',
            },
          }),
          async dispose() {},
        }
      },
    },
  }
  return { ctx, tools, getGuard: () => guard, getGoal: () => goal, workspace }
}

function execution(workspace) {
  return {
    agent: { session: { header: { cwd: workspace } } },
    signal: new AbortController().signal,
    concludeTurn() {},
  }
}

test('mounts only the domain surface and gates completion through validation and review', async t => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-plugin-contract-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  const harness = fakeContext(workspace)
  apply(harness.ctx)

  assert.equal(typeof harness.getGuard(), 'function')
  assert.match(harness.getGuard()({ name: 'write', arguments: { file_path: 'article.md' } }), /disabled/)
  assert.equal(harness.getGuard()({ name: 'read', arguments: { file_path: 'article.md' } }), undefined)
  assert.deepEqual([...harness.tools.keys()], [
    'initialize_publication',
    'resume_publication',
    'publication_status',
    'commit_chunk',
    'revise_chunk',
    'review_publication',
    'finalize_publication',
  ])

  const exec = execution(workspace)
  await harness.tools.get('initialize_publication').execute({
    project: {
      title: 'Plugin contract',
      objective: 'Complete a DSH-native plugin contract test',
      audience: 'engineers',
      language: 'en',
      sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain the contract', target_words: 8 }],
    },
  }, exec)
  await harness.tools.get('commit_chunk').execute({
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'This complete contract article contains enough substantive words for deterministic publication validation.',
  }, exec)
  const result = await harness.tools.get('finalize_publication').execute({}, exec)
  assert.equal(result.finalized, true)
  assert.equal(harness.getGoal().phase, 'complete')
})
