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

const missingGlyphMetricOptions = {
  platform: 'darwin',
  runner: async runs => runs.map(run => ({
    width: [...run.text].length * run.font_size * 0.55,
    ascent: run.font_size * 0.75,
    descent: run.font_size * 0.25,
    resolved_font_name: 'TestFont-Regular',
    missing_characters: run.text.includes('ₖ') ? ['ₖ'] : [],
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
    '<circle id="source-node" cx="30" cy="55" r="12" fill="#268bd2"/>',
    '<line id="flow-line" x1="50" y1="55" x2="165" y2="55" stroke="#222222"/>',
    '<text id="tiny-label" x="10" y="20" font-size="8" fill="#aaaaaa">Tiny</text>',
    '<text id="overlap-label" x="10" y="20" font-size="16" fill="#000000">Overlap</text>',
    '<text id="clipped-label" transform="translate(210 0)" x="10" y="100" font-size="16" fill="#000000">Clipped</text>',
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
  assert.ok(result.issues.some(item => item.includes('left_id="tiny-label"') && item.includes('right_id="overlap-label"')))
  assert.equal(result.metrics.text_boxes[0].id, 'tiny-label')
  assert.equal(result.metrics.shape_boxes.find(item => item.id === 'flow-line')?.tag, 'line')
})

test('hidden exact text cannot satisfy a required label', async () => {
  const source = svg([
    '<text id="hidden-exact" x="20" y="40" opacity="0" font-size="16">QKᵀ/√dₖ</text>',
    '<text id="visible-fallback" x="20" y="80" font-size="16">QK^T/√d_k</text>',
  ].join('\n'))
  const result = await preflightSvg(source, {
    required_labels: ['QKᵀ/√dₖ'],
    metricOptions,
  })
  assert.equal(result.passed, false)
  assert.ok(result.issues.includes('required_label_missing:QKᵀ/√dₖ'))
  assert.equal(result.metrics.text_boxes.some(item => item.id === 'hidden-exact'), false)
})

test('visible typographic text may carry an equivalent accessible exact label', async () => {
  const source = svg(
    '<text id="visible-formula" aria-label="QKᵀ/√dₖ" x="20" y="60" font-size="16">QK<tspan baseline-shift="super">T</tspan>/√d<tspan baseline-shift="sub">k</tspan></text>',
  )
  const result = await preflightSvg(source, {
    required_labels: ['QKᵀ/√dₖ'],
    metricOptions,
  })
  assert.equal(result.required_labels[0].present, true, result.issues.join('\n'))
  assert.equal(result.issues.some(item => item.startsWith('aria_label_not_visually_equivalent:')), false)
  assert.equal(result.issues.includes('required_label_missing:QKᵀ/√dₖ'), false)
  assert.equal(result.metrics.text_boxes[0].semantic_label, 'QKᵀ/√dₖ')
})

test('aria label must be visually equivalent and explicit font gaps fail preflight', async () => {
  const source = svg(
    '<text id="bad-formula" aria-label="QKᵀ/√dₖ" x="20" y="60" font-family="Test Font" font-size="16">unrelated ₖ</text>',
  )
  const result = await preflightSvg(source, {
    required_labels: ['QKᵀ/√dₖ'],
    metricOptions: missingGlyphMetricOptions,
  })
  assert.equal(result.passed, false)
  assert.ok(result.issues.some(item => item.startsWith('aria_label_not_visually_equivalent:')))
  assert.ok(result.issues.some(item => item.startsWith('text_unstable_glyph_run:') && item.includes('text_id="bad-formula"')))
  assert.ok(result.issues.includes('required_label_missing:QKᵀ/√dₖ'))
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

test('preflight rejects prose-heavy, undersized, and badly balanced compositions', async () => {
  const labels = Array.from({ length: 25 }, (_, index) => (
    `<text x="${20 + (index % 5) * 70}" y="${24 + Math.floor(index / 5) * 28}" font-size="12" fill="#111827">Verbose label ${index + 1}</text>`
  )).join('\n')
  const source = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">',
    '<rect width="960" height="540" fill="#ffffff"/>',
    '<rect x="15" y="15" width="380" height="150" fill="#eff6ff"/>',
    labels,
    '</svg>',
  ].join('\n')
  const result = await preflightSvg(source, {
    design_brief: {
      figure_type: 'process',
      publication_width: 'double_column',
      scientific_claim: 'A synthetic process proceeds from input to output.',
      scientific_checks: ['The input precedes the output.'],
      reading_order: ['Input', 'Output'],
    },
    metricOptions,
  })
  assert.equal(result.passed, false)
  assert.ok(result.issues.some(item => item.startsWith('text_item_count_exceeds_profile:')))
  assert.ok(result.issues.some(item => item.startsWith('text_below_minimum_font_size:')))
  assert.ok(result.issues.some(item => item.startsWith('content_balance_off_center:')))
})

test('preflight reports design metrics for a balanced publication-scale figure', async () => {
  const source = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">',
    '<rect width="960" height="540" fill="#ffffff"/>',
    '<text x="480" y="100" text-anchor="middle" font-size="26" fill="#0f172a">Balanced process</text>',
    '<rect x="80" y="190" width="220" height="130" rx="18" fill="#dbeafe"/>',
    '<rect x="660" y="190" width="220" height="130" rx="18" fill="#dcfce7"/>',
    '<line x1="300" y1="255" x2="660" y2="255" stroke="#334155" stroke-width="4"/>',
    '<text x="190" y="260" text-anchor="middle" font-size="22" fill="#0f172a">Input</text>',
    '<text x="480" y="225" text-anchor="middle" font-size="18" fill="#334155">Transform</text>',
    '<text x="770" y="260" text-anchor="middle" font-size="22" fill="#0f172a">Output</text>',
    '</svg>',
  ].join('\n')
  const result = await preflightSvg(source, {
    required_labels: ['Input', 'Output'],
    design_brief: {
      figure_type: 'process',
      publication_width: 'double_column',
      scientific_claim: 'The transform maps an input to an output.',
      scientific_checks: ['The arrow runs from Input to Output.'],
      reading_order: ['Input', 'Transform', 'Output'],
    },
    metricOptions,
  })
  assert.equal(result.passed, true, result.issues.join('\n'))
  assert.equal(result.metrics.design.figure_type, 'process')
  assert.equal(result.metrics.design.text_item_count, 4)
  assert.ok(result.metrics.design.content_center_offset < 0.1)
})

test('preflight does not treat a connector as a text background but detects its text collision', async () => {
  const source = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">',
    '<rect width="960" height="540" fill="#ffffff"/>',
    '<rect x="80" y="170" width="220" height="160" fill="#dbeafe"/>',
    '<rect x="660" y="170" width="220" height="160" fill="#dcfce7"/>',
    '<line x1="300" y1="180" x2="660" y2="320" stroke="#000000" stroke-width="4"/>',
    '<text x="480" y="256" text-anchor="middle" font-size="20" fill="#2563eb">Connector label</text>',
    '</svg>',
  ].join('\n')
  const result = await preflightSvg(source, { metricOptions })
  assert.equal(result.issues.some(item => item.startsWith('text_contrast_below_')), false, result.issues.join('\n'))
  assert.equal(result.issues.some(item => item.startsWith('connector_too_close_to_text:')), true, result.issues.join('\n'))
  assert.ok(result.issues.some(item => item.includes('"Connector label"') && item.endsWith(':line')), result.issues.join('\n'))
})

test('preflight enforces eight-point text at the planned publication width', async () => {
  const source = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">',
    '<rect width="960" height="540" fill="#ffffff"/>',
    '<rect x="80" y="180" width="800" height="180" fill="#eff6ff"/>',
    '<text x="480" y="280" text-anchor="middle" font-size="20" fill="#0f172a">Readable only at double-column width</text>',
    '</svg>',
  ].join('\n')
  const single = await preflightSvg(source, {
    design_brief: {
      figure_type: 'conceptual',
      publication_width: 'single_column',
      scientific_claim: 'A label is readable at its planned width.',
      scientific_checks: ['The label is visible.'],
      reading_order: ['Label'],
    },
    metricOptions,
  })
  const double = await preflightSvg(source, {
    design_brief: {
      figure_type: 'conceptual',
      publication_width: 'double_column',
      scientific_claim: 'A label is readable at its planned width.',
      scientific_checks: ['The label is visible.'],
      reading_order: ['Label'],
    },
    metricOptions,
  })
  assert.ok(single.issues.some(item => item.startsWith('text_below_minimum_font_size:')))
  assert.equal(double.issues.some(item => item.startsWith('text_below_minimum_font_size:')), false, double.issues.join('\n'))
  assert.ok(single.metrics.design.minimum_font_size > double.metrics.design.minimum_font_size)
})
