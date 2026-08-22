import assert from 'node:assert/strict'
import test from 'node:test'

import { preflightSvg } from '../svg/preflight.js'

const metricOptions = {
  platform: 'darwin',
  runner: async runs => runs.map(run => ({
    width: [...run.text].length * run.font_size * 0.55,
    ascent: run.font_size * 0.75,
    descent: run.font_size * 0.25,
  })),
}

function svg(body) {
  return [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 120">',
    '<rect width="220" height="120" fill="#ffffff"/>',
    body,
    '</svg>',
  ].join('\n')
}

test('preflight uses injected CoreText metrics, transforms, labels, and bounded geometry', async () => {
  const source = svg([
    '<circle cx="30" cy="55" r="12" fill="#268bd2"/>',
    '<line x1="50" y1="55" x2="165" y2="55" stroke="#222222"/>',
    '<text x="65" y="32" font-size="16" fill="#000000">Input</text>',
    '<text transform="translate(80 0)" x="65" y="88" font-size="16" fill="#000000">Output</text>',
  ].join('\n'))
  const result = await preflightSvg(source, {
    required_labels: ['Input', 'Output'],
    metricOptions,
  })
  assert.equal(result.passed, true, result.issues.join('\n'))
  assert.equal(result.metric_mode, 'coretext')
  assert.deepEqual(result.required_labels, [
    { label: 'Input', present: true },
    { label: 'Output', present: true },
  ])
  assert.equal(result.metrics.text_boxes[1].box.left > 140, true)
})

test('preflight reports clipping, overlap, small text, contrast, and missing labels', async () => {
  const source = svg([
    '<circle cx="30" cy="55" r="12" fill="#268bd2"/>',
    '<line x1="50" y1="55" x2="165" y2="55" stroke="#222222"/>',
    '<text x="10" y="20" font-size="8" fill="#aaaaaa">Tiny</text>',
    '<text x="10" y="20" font-size="16" fill="#000000">Overlap</text>',
    '<text transform="translate(210 0)" x="10" y="100" font-size="16" fill="#000000">Clipped</text>',
  ].join('\n'))
  const result = await preflightSvg(source, {
    required_labels: ['Absent'],
    metricOptions,
  })
  assert.equal(result.passed, false)
  assert.ok(result.issues.some(item => item.startsWith('text_below_minimum_font_size:')))
  assert.ok(result.issues.some(item => item.startsWith('text_contrast_below_4.5:')))
  assert.ok(result.issues.some(item => item.startsWith('text_overlap:')))
  assert.ok(result.issues.some(item => item.startsWith('text_outside_viewbox:')))
  assert.ok(result.issues.includes('required_label_missing:Absent'))
})

test('preflight rejects non-containing rectangle collisions unless they are explicitly allowed', async () => {
  const source = svg([
    '<rect x="10" y="10" width="100" height="60" fill="#ddeeff"/>',
    '<rect x="80" y="20" width="100" height="60" fill="#eeeeee"/>',
    '<line x1="20" y1="100" x2="180" y2="100" stroke="#222222"/>',
    '<text x="20" y="105" font-size="16" fill="#000000">Label</text>',
  ].join('\n'))
  const result = await preflightSvg(source, { metricOptions })
  assert.equal(result.passed, false)
  assert.ok(result.issues.some(item => item.startsWith('rect_overlap:')))
})
