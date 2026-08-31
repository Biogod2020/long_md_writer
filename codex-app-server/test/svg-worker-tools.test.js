import assert from 'node:assert/strict'
import test from 'node:test'

import {
  compactWorkerPreflight,
  SvgWorkerPreflight,
  SVG_PREFLIGHT_CANDIDATE_TOOL_SPEC,
  SVG_PREFLIGHT_DRAFT_TOOL_SPEC,
} from '../app-server/svg-worker-tools.js'

const PLAN = {
  required_labels: ['Input', 'Output'],
  design_brief: {
    figure_type: 'process',
    publication_width: 'double_column',
    scientific_claim: 'Input flows to output.',
    scientific_checks: ['The arrow points from Input to Output.'],
    reading_order: ['Input', 'Output'],
  },
}

const SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" id="root" viewBox="0 0 960 540">',
  '<rect id="background" width="960" height="540" fill="#ffffff"/>',
  '<rect id="input-box" x="80" y="180" width="220" height="150" rx="18" fill="#dbeafe"/>',
  '<rect id="output-box" x="660" y="180" width="220" height="150" rx="18" fill="#dcfce7"/>',
  '<line id="flow" x1="300" y1="255" x2="660" y2="255" stroke="#334155" stroke-width="4"/>',
  '<text id="input-label" x="190" y="260" text-anchor="middle" font-size="22" fill="#0f172a">Input</text>',
  '<text id="output-label" x="770" y="260" text-anchor="middle" font-size="22" fill="#0f172a">Output</text>',
  '</svg>',
].join('\n')

test('SVG worker preflight tools are separate read-only candidate and draft checks', () => {
  assert.equal(SVG_PREFLIGHT_CANDIDATE_TOOL_SPEC.name, 'svg_preflight_candidate')
  assert.deepEqual(SVG_PREFLIGHT_CANDIDATE_TOOL_SPEC.inputSchema.required, ['svg'])
  assert.equal(SVG_PREFLIGHT_DRAFT_TOOL_SPEC.name, 'svg_preflight_draft')
  assert.deepEqual(SVG_PREFLIGHT_DRAFT_TOOL_SPEC.inputSchema.properties, {})
})

test('worker preflight returns compact id-addressed targets and enforces its check budget', async () => {
  const preflight = new SvgWorkerPreflight(PLAN, { maximumChecks: 1 })
  const result = await preflight.inspect(SVG)
  assert.equal(result.passed, true, result.issues.join('\n'))
  assert.equal(result.remaining_checks, 0)
  assert.equal(result.editable_targets.texts[0].id, 'input-label')
  assert.ok(result.editable_targets.shapes.some(item => item.id === 'flow'))
  assert.match(result.instruction, /emit the required final structured JSON/i)
  await assert.rejects(preflight.inspect(SVG), /budget exhausted.*deliver/i)
})

test('compact worker preflight preserves exact issue ids without returning an unbounded report', () => {
  const issues = Array.from({ length: 40 }, (_, index) => `text_overlap:${index}:left_id="a-${index}"`)
  const compact = compactWorkerPreflight({
    passed: false,
    source_sha256: 'a'.repeat(64),
    metric_mode: 'coretext',
    issues,
    warnings: Array.from({ length: 12 }, (_, index) => `warning-${index}`),
    required_labels: [],
    metrics: { text_boxes: [], shape_boxes: [], design: { figure_type: 'process' } },
  }, 1, 3)
  assert.equal(compact.issue_count, 40)
  assert.equal(compact.issues.length, 32)
  assert.equal(compact.warnings.length, 8)
  assert.equal(compact.issues[0], 'text_overlap:0:left_id="a-0"')
})
