import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  appendVisualPreflight,
  appendVisualReview,
  initializeProject,
  readAssetManifest,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
} from '../lib/project-store.js'
import { submitSvg } from '../svg/submit.js'
import { preflightAsset, recordAssetReview } from '../svg/workflow.js'

const SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 120">',
  '<rect width="220" height="120" fill="#ffffff"/>',
  '<circle cx="30" cy="55" r="12" fill="#268bd2"/>',
  '<line x1="50" y1="55" x2="165" y2="55" stroke="#222222"/>',
  '<text x="65" y="32" font-size="16" fill="#000000">Flow</text>',
  '</svg>',
].join('\n')

const metricOptions = {
  platform: 'darwin',
  runner: async runs => runs.map(run => ({
    width: [...run.text].length * run.font_size * 0.55,
    ascent: run.font_size * 0.75,
    descent: run.font_size * 0.25,
  })),
}

async function fixture(t) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-svg-workflow-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, {
    title: 'Workflow fixture',
    objective: 'Verify SVG visual evidence',
    audience: 'engineers',
    language: 'en',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain evidence', target_words: 8 }],
    visual_contract: {
      figures: [{
        id: 'flow-figure',
        section_id: 'intro',
        kind: 'diagram',
        purpose: 'Show the evidence flow.',
        required_labels: ['Flow'],
      }],
    },
  })
  return workspace
}

function dependencies() {
  return {
    registerAsset,
    resolveVisualPlan,
    readRegisteredAsset,
    readAssetManifest,
    appendVisualPreflight,
    appendVisualReview,
    metricOptions,
    renderSvgToPng: async () => ({
      png: Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0]),
      backend: 'test-renderer',
    }),
  }
}

test('preflight retains a preview and review evidence bound to one planned SVG', async t => {
  const workspace = await fixture(t)
  const submitted = await submitSvg(workspace, {
    svg: SVG,
    id: 'flow-svg',
    caption: 'Workflow flow diagram',
    alt_text: 'A labelled Flow diagram.',
    visual_plan_id: 'flow-figure',
    used_in: ['intro'],
  }, dependencies())
  assert.equal(submitted.status, 'registered')

  const preflight = await preflightAsset(workspace, { asset_id: submitted.asset_id }, dependencies())
  assert.equal(preflight.status, 'passed', preflight.reason ?? preflight.report?.issues.join('\n'))
  assert.match(preflight.preview_asset_path, /^assets\/reviews\/preview-/)
  assert.match(preflight.preflight_id, /^preflight-/)

  const reviewed = await recordAssetReview(workspace, {
    asset_id: submitted.asset_id,
    preflight_id: preflight.preflight_id,
    reviewer: 'reviewer-1',
    verdict: 'pass',
    summary: 'The retained PNG is readable and visibly contains Flow.',
    findings: [],
    checked_labels: ['Flow'],
  }, dependencies())
  assert.equal(reviewed.status, 'recorded_pass')
  const manifest = await readAssetManifest(workspace)
  assert.equal(manifest.assets.length, 2)
  assert.equal(manifest.visual_preflights[0].asset_sha256, submitted.asset_sha256)
  assert.equal(manifest.visual_reviews[0].preview_sha256, preflight.preview_sha256)
})

test('a passing review cannot omit a required visual label', async t => {
  const workspace = await fixture(t)
  const submitted = await submitSvg(workspace, {
    svg: SVG,
    id: 'flow-svg',
    caption: 'Workflow flow diagram',
    alt_text: 'A labelled Flow diagram.',
    visual_plan_id: 'flow-figure',
    used_in: ['intro'],
  }, dependencies())
  const preflight = await preflightAsset(workspace, { asset_id: submitted.asset_id }, dependencies())
  const reviewed = await recordAssetReview(workspace, {
    asset_id: submitted.asset_id,
    preflight_id: preflight.preflight_id,
    reviewer: 'reviewer-1',
    verdict: 'pass',
    summary: 'Claimed pass without confirming the required label.',
    checked_labels: [],
  }, dependencies())
  assert.equal(reviewed.status, 'error')
  assert.match(reviewed.reason, /confirm every required label/)
})

test('a failed candidate can be superseded without rewriting its historical evidence', async t => {
  const workspace = await fixture(t)
  const failedSource = SVG.replace('font-size="16"', 'font-size="8"')
  const first = await submitSvg(workspace, {
    svg: failedSource,
    id: 'flow-svg-v1',
    caption: 'First flow diagram candidate',
    alt_text: 'A too-small labelled Flow diagram.',
    visual_plan_id: 'flow-figure',
    used_in: ['intro'],
  }, dependencies())
  const failed = await preflightAsset(workspace, { asset_id: first.asset_id }, dependencies())
  assert.equal(failed.status, 'failed')
  assert.ok(failed.report.issues.some(item => item.startsWith('text_below_minimum_font_size:')))

  const corrected = await submitSvg(workspace, {
    svg: SVG,
    id: 'flow-svg-v2',
    caption: 'Corrected flow diagram candidate',
    alt_text: 'A readable labelled Flow diagram.',
    visual_plan_id: 'flow-figure',
    supersedes_asset_id: first.asset_id,
    used_in: ['intro'],
  }, dependencies())
  assert.equal(corrected.status, 'registered')
  const passing = await preflightAsset(workspace, { asset_id: corrected.asset_id }, dependencies())
  assert.equal(passing.status, 'passed', passing.reason ?? passing.report?.issues.join('\n'))
  const manifest = await readAssetManifest(workspace)
  const firstEntry = manifest.assets.find(entry => entry.id === first.asset_id)
  const secondEntry = manifest.assets.find(entry => entry.id === corrected.asset_id)
  assert.equal(secondEntry.supersedes_asset_id, firstEntry.id)
  assert.equal(manifest.visual_preflights.length, 2)
})
