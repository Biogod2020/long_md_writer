import assert from 'node:assert/strict'
import test from 'node:test'

import { SvgDraftEditor, SVG_EDIT_TOOL_SPEC } from '../app-server/svg-draft-editor.js'

const BASELINE = `
<svg xmlns="http://www.w3.org/2000/svg" id="diagram" viewBox="0 0 600 300">
  <g id="input-group" transform="translate(40 80)">
    <rect id="input-box" x="0" y="0" width="160" height="80" fill="#dbeafe"/>
    <text id="input-label" x="80" y="46" font-size="20" text-anchor="middle">Input</text>
  </g>
  <path id="main-arrow" d="M 210 120 L 380 120" stroke="#334155" stroke-width="4"/>
  <g id="output-group" transform="translate(390 80)">
    <rect id="output-box" x="0" y="0" width="160" height="80" fill="#dcfce7"/>
    <text id="output-label" x="80" y="46" font-size="20" text-anchor="middle">Output</text>
  </g>
</svg>`.trim()

test('svg_edit applies local id-addressed edits while retaining the rest of the champion', () => {
  const editor = new SvgDraftEditor(BASELINE)
  const moved = editor.edit({
    action: 'set_attributes',
    target_id: 'output-group',
    attributes: [{ name: 'transform', value: 'translate(390 130)' }],
  })
  const relabelled = editor.edit({ action: 'set_text', target_id: 'output-label', text: 'Final output' })

  assert.equal(moved.revision, 1)
  assert.equal(relabelled.revision, 2)
  assert.match(editor.source, /id="input-group" transform="translate\(40 80\)"/)
  assert.match(editor.source, /id="output-group" transform="translate\(390 130\)"/)
  assert.match(editor.source, />Final output<\/text>/)
  assert.deepEqual(Object.keys(SVG_EDIT_TOOL_SPEC.inputSchema.properties).sort(), [
    'action',
    'attributes',
    'fragment',
    'operations',
    'target_id',
    'text',
  ])
})

test('svg_edit applies coordinated id-addressed operations atomically in one revision', () => {
  const editor = new SvgDraftEditor(BASELINE)
  const result = editor.edit({
    operations: [
      {
        action: 'set_attributes',
        target_id: 'output-group',
        attributes: [{ name: 'transform', value: 'translate(390 130)' }],
      },
      { action: 'set_text', target_id: 'output-label', text: 'Final output' },
      { action: 'remove', target_id: 'main-arrow' },
    ],
  })

  assert.equal(result.revision, 1)
  assert.equal(result.operation_count, 3)
  assert.equal(result.action, 'batch')
  assert.equal(result.operations.length, 3)
  assert.match(editor.source, /translate\(390 130\)/)
  assert.match(editor.source, />Final output<\/text>/)
  assert.doesNotMatch(editor.source, /id="main-arrow"/)
})

test('svg_edit rejects an invalid batch without retaining earlier operations', () => {
  const editor = new SvgDraftEditor(BASELINE)
  const before = editor.source
  assert.throws(() => editor.edit({
    operations: [
      { action: 'set_text', target_id: 'output-label', text: 'Would be lost' },
      { action: 'remove', target_id: 'diagram' },
    ],
  }), /cannot remove the root/i)
  assert.equal(editor.source, before)
  assert.equal(editor.revision, 0)
})

test('svg_edit validates a transaction before replacing its in-memory draft', () => {
  const editor = new SvgDraftEditor(BASELINE)
  const before = editor.source
  assert.throws(() => editor.edit({
    action: 'set_attributes',
    target_id: 'input-box',
    attributes: [{ name: 'style', value: 'fill:url(https://example.test/unsafe.svg)' }],
  }), /rejected the transaction.*unsafe_css_reference/i)
  assert.equal(editor.source, before)
  assert.equal(editor.revision, 0)
})

test('svg_edit rejects duplicate ids and cannot replace or remove the root source', () => {
  const editor = new SvgDraftEditor(BASELINE)
  assert.throws(() => editor.edit({
    action: 'append_fragment',
    target_id: 'diagram',
    fragment: '<circle id="input-box" cx="10" cy="10" r="4"/>',
  }), /duplicate editable id/i)
  assert.throws(() => editor.edit({ action: 'remove', target_id: 'diagram' }), /cannot remove the root/i)
  assert.equal(editor.revision, 0)
})

test('svg_edit enforces a per-worker edit budget and tells the worker to deliver', () => {
  const editor = new SvgDraftEditor(BASELINE, { maxEdits: 2 })
  editor.edit({ action: 'set_text', target_id: 'input-label', text: 'Desired input' })
  const finalEdit = editor.edit({ action: 'set_text', target_id: 'output-label', text: 'Measured output' })
  const retained = editor.source
  assert.equal(finalEdit.remaining_edits, 0)
  assert.match(finalEdit.instruction, /emit the final structured JSON/i)
  assert.throws(
    () => editor.edit({ action: 'remove', target_id: 'main-arrow' }),
    /budget exhausted.*do not call svg_edit again/i,
  )
  assert.equal(editor.source, retained)
  assert.equal(editor.revision, 2)
})
