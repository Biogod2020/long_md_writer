import assert from 'node:assert/strict'
import test from 'node:test'

import { checkMermaidSource, mermaidAssetId, mermaidSourceId } from '../mermaid/core.js'

const SOURCE = `flowchart LR
  accTitle: Publication flow
  accDescr: Sources become a reviewed article
  A[Sources] --> B[Article]
`

test('accepts bounded common Mermaid and reports its diagram type', () => {
  const result = checkMermaidSource(SOURCE)
  assert.equal(result.accepted, true)
  assert.equal(result.metrics.diagram_type, 'flowchart')
  assert.deepEqual(result.errors, [])
})

test('rejects renderer directives, active clicks, external URLs, and unknown declarations', () => {
  for (const source of [
    '%%{init: {"theme":"dark"}}%%\nflowchart LR\nA-->B',
    'flowchart LR\nA-->B\nclick A callback',
    'flowchart LR\nA[https://example.com]-->B',
    'unknownDiagram\nA-->B',
  ]) {
    assert.equal(checkMermaidSource(source).accepted, false)
  }
})

test('derives separate stable content ids for Mermaid source and rendered asset', () => {
  assert.match(mermaidSourceId(SOURCE), /^mermaid-src-[a-f0-9]{20}$/)
  assert.match(mermaidAssetId(SOURCE), /^mermaid-[a-f0-9]{20}$/)
  assert.notEqual(mermaidSourceId(SOURCE), mermaidAssetId(SOURCE))
  assert.equal(mermaidSourceId(SOURCE), mermaidSourceId(SOURCE))
})
