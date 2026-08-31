import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { Resvg } from '@resvg/resvg-js'

import {
  appendImageSearchReceipt,
  appendVisualPreflight,
  initializeProject,
  readAssetManifest,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
  setVisualContract,
} from '../lib/project-store.js'
import { submitWebImage } from '../image/submit.js'

function pngBytes(label = 'ECG') {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#f4f4f4"/><text x="24" y="48" font-size="28">${label}</text></svg>`
  return Buffer.from(new Resvg(svg).render().asPng())
}

async function workspace(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'longwriter-image-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await initializeProject(root, {
    title: 'Photo test',
    objective: 'Register a searched clinical photo',
    audience: 'medical students',
    language: 'zh',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Show a real ECG machine', target_words: 10 }],
  })
  await setVisualContract(root, {
    figures: [{
      id: 'ecg-machine',
      section_id: 'intro',
      kind: 'photo',
      purpose: 'Show a real electrocardiograph used at the bedside.',
      required_labels: ['ECG'],
    }],
  })
  await appendImageSearchReceipt(root, {
    status: 'ok',
    query: 'bedside ECG machine',
    provider: 'bing_images',
    results: [{
      source_id: 'candidate-1',
      rank: 1,
      title: 'ECG machine',
      murl: 'https://images.example.test/ecg-machine.png',
      purl: 'https://example.test/ecg-guide',
      width: 400,
      height: 300,
      score: 90,
      domain_hint: 'good',
    }],
  })
  return root
}

function input(extra = {}) {
  return {
    image_url: 'https://images.example.test/ecg-machine.png',
    caption: '床旁心电图机',
    alt_text: 'A bedside electrocardiograph with limb leads attached.',
    visual_plan_id: 'ecg-machine',
    used_in: ['intro'],
    ...extra,
  }
}

function fetchPng(bytes = pngBytes()) {
  return async () => ({
    ok: true,
    status: 200,
    headers: { get: name => (name.toLowerCase() === 'content-type' ? 'image/png' : null) },
    arrayBuffer: async () => bytes,
  })
}

test('image_submit registers a retained search candidate as a local photo with preview', async t => {
  const root = await workspace(t)
  const bytes = pngBytes()
  const result = await submitWebImage(root, input(), {
    registerAsset,
    resolveVisualPlan,
    readAssetManifest,
    appendVisualPreflight,
    fetch: fetchPng(bytes),
  })
  assert.equal(result.status, 'registered')
  assert.match(result.asset.path, /^assets\/photos\/.+\.png$/)
  assert.equal(result.asset.visual_plan_id, 'ecg-machine')
  assert.match(result.preview.path, /^assets\/reviews\/.+\.png$/)
  assert.equal(result.preflight.metric_mode, 'photo')
  assert.equal(result.preflight.passed, true)
  const registered = await readRegisteredAsset(root, result.asset.id)
  assert.equal(registered.sha256, result.asset.sha256)
  const manifest = await readAssetManifest(root)
  assert.equal(manifest.assets.some(entry => entry.path === result.asset.path), true)
})

test('image_submit registers a public URL that was not previously searched', async t => {
  const root = await workspace(t)
  const result = await submitWebImage(root, input({ image_url: 'https://images.example.test/other.png' }), {
    registerAsset,
    resolveVisualPlan,
    readAssetManifest,
    appendVisualPreflight,
    fetch: fetchPng(),
  })
  assert.equal(result.status, 'registered')
  assert.equal(result.candidate.receipt_id, null)
  assert.equal(result.candidate.image_url, 'https://images.example.test/other.png')
})

test('image_submit rejects a non-photo visual plan', async t => {
  const root = await workspace(t)
  await setVisualContract(root, {
    figures: [{
      id: 'axis',
      section_id: 'intro',
      kind: 'svg',
      purpose: 'Diagram only.',
      required_labels: ['Axis'],
    }],
  })
  await assert.rejects(
    submitWebImage(root, input({ visual_plan_id: 'axis' }), {
      registerAsset,
      resolveVisualPlan,
      readAssetManifest,
      appendVisualPreflight,
      fetch: fetchPng(),
    }),
    /kind photo/,
  )
})
