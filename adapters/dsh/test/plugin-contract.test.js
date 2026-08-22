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
              visual_findings: [],
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
    'plan_visuals',
    'resume_publication',
    'publication_status',
    'commit_chunk',
    'revise_chunk',
    'review_publication',
    'finalize_publication',
    'svg_check',
    'svg_submit',
    'svg_preflight',
    'svg_record_review',
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
  const svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">',
    '<rect width="100" height="60" fill="#fff"/>',
    '<circle cx="25" cy="20" r="12" fill="#268bd2"/>',
    '<line x1="42" y1="20" x2="82" y2="20" stroke="#222"/>',
    '<text x="50" y="54" text-anchor="middle">Flow</text>',
    '</svg>',
  ].join('\n')
  const planned = await harness.tools.get('plan_visuals').execute({
    visual_contract: {
      figures: [{
        id: 'contract-flow-figure',
        section_id: 'intro',
        kind: 'diagram',
        purpose: 'Show the controlled publication flow.',
        required_labels: ['Flow'],
      }],
    },
  }, exec)
  assert.equal(planned.planned, true)
  const checked = await harness.tools.get('svg_check').execute({ svg }, exec)
  assert.equal(checked.accepted, true)
  const submitted = await harness.tools.get('svg_submit').execute({
    svg,
    id: 'contract-flow',
    caption: 'Contract flow diagram',
    alt_text: 'A simple circle-to-line flow diagram.',
    used_in: ['intro'],
    visual_plan_id: 'contract-flow-figure',
  }, exec)
  assert.equal(submitted.status, 'registered')
  assert.equal(submitted.asset_path, 'assets/svg/contract-flow.svg')
  const preflight = await harness.tools.get('svg_preflight').execute({ asset_id: 'contract-flow' }, exec)
  assert.equal(preflight.status, 'passed')
  assert.match(preflight.preview_asset_path, /^assets\/reviews\/preview-/)
  const reviewed = await harness.tools.get('svg_record_review').execute({
    asset_id: 'contract-flow',
    preflight_id: preflight.preflight_id,
    reviewer: 'independent-reviewer',
    verdict: 'pass',
    summary: 'The retained preview is readable and contains the planned Flow label.',
    findings: [],
    checked_labels: ['Flow'],
  }, exec)
  assert.equal(reviewed.status, 'recorded_pass')
  await harness.tools.get('commit_chunk').execute({
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'This complete contract article contains enough substantive words for deterministic publication validation.\n\n![A simple circle-to-line flow diagram.](assets/svg/contract-flow.svg)',
  }, exec)
  const result = await harness.tools.get('finalize_publication').execute({}, exec)
  assert.equal(result.finalized, true)
  assert.equal(harness.getGoal().phase, 'complete')
})
