import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  initializeProject,
  readAssetManifest,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
  setVisualContract,
} from '../lib/project-store.js'
import { submitMermaid } from '../mermaid/submit.js'

const SOURCE = `flowchart LR
  accTitle: Publication flow
  accDescr: Sources become a reviewed article
  A[Sources] --> B[Article]
`

const SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80">',
  '<rect width="200" height="80" fill="#fff"/>',
  '<rect x="10" y="20" width="60" height="30" fill="#def"/>',
  '<line x1="70" y1="35" x2="120" y2="35" stroke="#222"/>',
  '<text x="40" y="40">Sources</text>',
  '<text x="150" y="40">Article</text>',
  '</svg>',
].join('\n')

async function workspace(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'longwriter-mermaid-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await initializeProject(root, {
    title: 'Mermaid test',
    objective: 'Test Mermaid source retention and rendering',
    audience: 'engineers',
    language: 'en',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain the flow', target_words: 10 }],
  })
  await setVisualContract(root, {
    figures: [{
      id: 'publication-flow',
      section_id: 'intro',
      kind: 'mermaid',
      purpose: 'Show the publication flow.',
      required_labels: ['Sources', 'Article'],
    }],
  })
  return root
}

function dependencies() {
  return {
    registerAsset,
    resolveVisualPlan,
    readAssetManifest,
    readRegisteredAsset,
    async renderMermaid() { return { svg: SVG, backend: 'mermaid-cli@11.16.0' } },
  }
}

function input(extra = {}) {
  return {
    mermaid: SOURCE,
    id: 'publication-flow-v1',
    caption: 'Publication flow',
    alt_text: 'Sources flow into an article.',
    visual_plan_id: 'publication-flow',
    used_in: ['intro'],
    ...extra,
  }
}

test('dry run renders and applies the exact SVG gate without writing assets', async t => {
  const root = await workspace(t)
  const result = await submitMermaid(root, input({ dry_run: true }), dependencies())
  assert.equal(result.status, 'checked')
  assert.equal(result.registered, false)
  assert.equal((await readAssetManifest(root)).assets.length, 0)
})

test('retains Mermaid source and registers a hash-bound SVG derivative', async t => {
  const root = await workspace(t)
  const result = await submitMermaid(root, input(), dependencies())
  assert.equal(result.status, 'registered')
  assert.equal(result.asset_path, 'assets/svg/publication-flow-v1.svg')
  assert.match(result.source_asset_path, /^assets\/mermaid\/mermaid-src-/)

  const manifest = await readAssetManifest(root)
  assert.equal(manifest.assets.length, 2)
  const source = manifest.assets.find(asset => asset.id === result.source_asset_id)
  const svg = manifest.assets.find(asset => asset.id === result.asset_id)
  assert.equal(source.path, result.source_asset_path)
  assert.deepEqual(svg.derivative_of, {
    asset_id: source.id,
    asset_sha256: source.sha256,
    purpose: 'rendered_from_mermaid_source',
  })
  assert.equal((await readRegisteredAsset(root, source.id)).bytes.toString('utf8'), SOURCE)
})

test('rejects unsafe Mermaid before invoking the renderer', async t => {
  const root = await workspace(t)
  let rendered = false
  const result = await submitMermaid(root, input({ mermaid: 'flowchart LR\nA-->B\nclick A "https://example.com"' }), {
    ...dependencies(),
    async renderMermaid() { rendered = true; return { svg: SVG, backend: 'test' } },
  })
  assert.equal(result.status, 'rejected')
  assert.equal(rendered, false)
})
