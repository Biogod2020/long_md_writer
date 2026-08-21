import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  initializeProject,
  readAssetManifest,
  registerAsset,
  resolveVisualPlan,
} from '../lib/project-store.js'
import { submitSvg } from '../svg/submit.js'

const VALID_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">',
  '<rect width="200" height="100" fill="#fff"/>',
  '<circle cx="50" cy="50" r="20" fill="#268bd2"/>',
  '<line x1="80" y1="50" x2="160" y2="50" stroke="#222"/>',
  '<text x="100" y="90" text-anchor="middle">Flow</text>',
  '</svg>',
].join('\n')

function project() {
  return {
    title: 'SVG submit test',
    objective: 'Verify controlled SVG registration',
    audience: 'engineers',
    language: 'en',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain SVG submission', target_words: 8 }],
    visual_contract: {
      figures: [{
        id: 'flow-figure',
        section_id: 'intro',
        kind: 'diagram',
        purpose: 'Show the controlled flow.',
        required_labels: ['Flow'],
      }],
    },
  }
}

async function fixture(t) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-svg-submit-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, project())
  return workspace
}

function input(overrides = {}) {
  return {
    svg: VALID_SVG,
    id: 'flow-diagram',
    caption: 'Controlled SVG flow diagram',
    alt_text: 'A blue circle connected to a labelled horizontal flow line.',
    used_in: ['intro'],
    visual_plan_id: 'flow-figure',
    ...overrides,
  }
}

test('dry run checks the same gate without registering a canonical asset', async t => {
  const workspace = await fixture(t)
  const result = await submitSvg(workspace, input({ dry_run: true }), { registerAsset, resolveVisualPlan })
  assert.equal(result.status, 'checked')
  assert.equal(result.accepted, true)
  assert.equal(result.registered, false)
  assert.equal((await readAssetManifest(workspace)).assets.length, 0)
})

test('re-checks and registers a valid SVG only through the domain store', async t => {
  const workspace = await fixture(t)
  const result = await submitSvg(workspace, input(), { registerAsset, resolveVisualPlan })
  assert.equal(result.status, 'registered')
  assert.equal(result.registered, true)
  assert.equal(result.asset_id, 'flow-diagram')
  assert.equal(result.asset_path, 'assets/svg/flow-diagram.svg')
  assert.match(result.asset_sha256, /^[a-f0-9]{64}$/)

  const manifest = await readAssetManifest(workspace)
  assert.deepEqual(manifest.assets[0], {
    id: 'flow-diagram',
    source: 'agent',
    path: 'assets/svg/flow-diagram.svg',
    caption: 'Controlled SVG flow diagram',
    alt_text: 'A blue circle connected to a labelled horizontal flow line.',
    provenance: 'agent_generated:svg-illustrator',
    licence: 'generated_internal',
    used_in: ['intro'],
    sha256: result.asset_sha256,
    visual_plan_id: 'flow-figure',
  })
  assert.equal(await readFile(path.join(workspace, result.asset_path), 'utf8'), VALID_SVG)
})

test('rejects unsafe SVG before it can reach registerAsset', async () => {
  let calls = 0
  const result = await submitSvg('/unused', input({
    svg: '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
  }), {
    registerAsset: async () => { calls += 1 },
    resolveVisualPlan,
  })
  assert.equal(result.status, 'rejected')
  assert.equal(result.accepted, false)
  assert.equal(calls, 0)
})

test('reports registration metadata errors without creating an asset', async t => {
  const workspace = await fixture(t)
  const result = await submitSvg(workspace, input({ caption: '' }), { registerAsset, resolveVisualPlan })
  assert.equal(result.status, 'error')
  assert.equal(result.accepted, true)
  assert.match(result.reason, /caption/)
  assert.equal((await readAssetManifest(workspace)).assets.length, 0)
})
