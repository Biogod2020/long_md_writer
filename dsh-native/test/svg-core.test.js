import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assetIdFor,
  checkSvg,
  resolvePolicy,
  scoreSvg,
  validateSvgSource,
} from '../svg/core.js'

const VALID_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">',
  '  <rect x="0" y="0" width="400" height="300" fill="#f4f4f4"/>',
  '  <circle cx="200" cy="120" r="60" fill="#2a7"/>',
  '  <line x1="80" y1="120" x2="320" y2="120" stroke="#333"/>',
  '  <text x="200" y="230" text-anchor="middle" font-size="20">ECG waveform</text>',
  '</svg>',
].join('\n')

test('resolves only bounded deterministic SVG policy', () => {
  assert.deepEqual(resolvePolicy({}), {
    maxElements: 400,
    maxChars: 60_000,
    acceptScore: 55,
  })
  assert.throws(() => resolvePolicy(null), /config must be an object/)
  assert.throws(() => resolvePolicy({ maxElements: 2 }), /maxElements/)
  assert.throws(() => resolvePolicy({ maxChars: 999 }), /maxChars/)
  assert.throws(() => resolvePolicy({ acceptScore: 101 }), /acceptScore/)
})

test('validates a self-contained well-formed SVG with explainable metrics', () => {
  const result = validateSvgSource(VALID_SVG)
  assert.equal(result.ok, true)
  assert.deepEqual(result.errors, [])
  assert.equal(result.metrics.safe, true)
  assert.equal(result.metrics.elementCount, 5)
  assert.deepEqual(result.metrics.dimensions, { width: 400, height: 300 })

  const score = scoreSvg(result.metrics)
  assert.equal(score.score, 100)
  assert.equal(score.label, 'good')
  assert.ok(score.signals.includes('has_text_labels'))
})

test('rejects malformed source, unsafe elements, handlers, and non-fragment references', () => {
  assert.equal(validateSvgSource('').ok, false)
  assert.equal(validateSvgSource('<svg><rect></svg>').ok, false)
  assert.ok(validateSvgSource('<!DOCTYPE svg><svg><rect/></svg>').errors.includes('doctype_or_entity_declared'))

  const script = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
  assert.ok(script.errors.includes('unsafe_tag:script'))

  const handler = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg" onclick="x()"><rect/></svg>')
  assert.ok(handler.errors.includes('event_handler:onclick'))

  const remote = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/x.png"/></svg>')
  assert.ok(remote.errors.includes('unsafe_reference:href'))

  const data = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AA=="/></svg>')
  assert.ok(data.errors.includes('unsafe_reference:href'))

  const css = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(https://example.com/x)"/></svg>')
  assert.ok(css.errors.includes('unsafe_css_reference:fill'))

  const style = validateSvgSource('<svg xmlns="http://www.w3.org/2000/svg"><style>@import url("https://example.com/x.css")</style><rect/></svg>')
  assert.ok(style.errors.includes('style_external_reference'))
})

test('allows local fragment references but bounds element count and source size', () => {
  const fragments = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">',
    '  <defs><linearGradient id="shade"><stop offset="0%"/></linearGradient><rect id="unit"/></defs>',
    '  <use href="#unit" fill="url(#shade)"/>',
    '</svg>',
  ].join('\n')
  assert.equal(validateSvgSource(fragments).ok, true)

  const many = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    + '<rect width="1" height="1"/>'.repeat(12)
    + '</svg>'
  assert.ok(validateSvgSource(many, { maxElements: 10 }).errors.some(error => error.startsWith('too_many_elements:')))
  assert.ok(validateSvgSource(VALID_SVG.repeat(10), { maxChars: 1_000 }).errors.some(error => error.startsWith('svg_too_large:')))
})

test('gates only a structurally valid SVG meeting the configured score', () => {
  const accepted = checkSvg(VALID_SVG)
  assert.equal(accepted.status, 'accepted')
  assert.equal(accepted.accepted, true)
  assert.equal(accepted.valid, true)
  assert.match(accepted.source_sha256, /^[a-f0-9]{64}$/)

  const sparse = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
  const defaultGate = checkSvg(sparse)
  assert.equal(defaultGate.valid, true)
  assert.equal(defaultGate.accepted, false)
  assert.equal(defaultGate.label, 'weak')
  assert.equal(checkSvg(sparse, { acceptScore: 45 }).accepted, true)

  const unsafe = checkSvg('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', { acceptScore: 0 })
  assert.equal(unsafe.valid, false)
  assert.equal(unsafe.accepted, false)
  assert.equal(unsafe.score, 0)
  assert.deepEqual(unsafe.signals, ['validation_failed'])
})

test('derives a stable source-hash asset id', () => {
  assert.equal(assetIdFor(VALID_SVG), assetIdFor(VALID_SVG))
  assert.notEqual(assetIdFor(VALID_SVG), assetIdFor('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'))
  assert.match(assetIdFor(VALID_SVG), /^svg-[a-f0-9]{12}$/)
  assert.throws(() => assetIdFor(''), /non-empty/)
})
