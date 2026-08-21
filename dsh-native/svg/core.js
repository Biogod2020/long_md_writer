/**
 * Model- and harness-independent SVG safety gate.
 *
 * This module does not generate, repair, or visually judge diagrams. An
 * agent creates the SVG; this module provides deterministic checks and an
 * explainable baseline score before an asset can be registered.
 *
 * @module longwriter/svg-core
 */

import { createHash } from 'node:crypto'
import { DOMParser } from '@xmldom/xmldom'

export const DEFAULT_MAX_ELEMENTS = 400
export const DEFAULT_MAX_CHARS = 60_000
export const DEFAULT_ACCEPT_SCORE = 55
export const GOOD_SCORE = 55
export const WEAK_SCORE = 30

const UNSAFE_TAGS = new Set([
  'script', 'foreignobject', 'iframe', 'object', 'embed',
])
const DOCTYPE_RE = /<!DOCTYPE|<!ENTITY/i
const STYLE_IMPORT_RE = /@import/i
const CSS_URL_RE = /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]+))\s*\)/gi

function boundedInteger(value, name, fallback, minimum, maximum) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isInteger(resolved) || resolved < minimum || resolved > maximum) {
    throw new Error('svg policy: ' + name + ' must be an integer in ' + minimum + '..' + maximum)
  }
  return resolved
}

function boundedNumber(value, name, fallback, minimum, maximum) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isFinite(resolved) || resolved < minimum || resolved > maximum) {
    throw new Error('svg policy: ' + name + ' must be a number in ' + minimum + '..' + maximum)
  }
  return resolved
}

/**
 * Resolve the bounded, deterministic policy accepted by all entry points.
 * No policy member controls a model, timeout, route, or retry loop.
 */
export function resolvePolicy(input = {}) {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('svg policy: config must be an object')
  }
  return {
    maxElements: boundedInteger(input.maxElements, 'maxElements', DEFAULT_MAX_ELEMENTS, 10, 5_000),
    maxChars: boundedInteger(input.maxChars, 'maxChars', DEFAULT_MAX_CHARS, 1_000, 500_000),
    acceptScore: boundedNumber(input.acceptScore, 'acceptScore', DEFAULT_ACCEPT_SCORE, 0, 100),
  }
}

function parser() {
  const errors = []
  return {
    parseFromString(source, mimeType) {
      const doc = new DOMParser({
        onError: (_level, message) => errors.push(message),
      }).parseFromString(source, mimeType)
      return { doc, errors }
    },
  }
}

function isFragmentReference(value) {
  return value.trim().startsWith('#')
}

function hasUnsafeCssReference(value) {
  CSS_URL_RE.lastIndex = 0
  for (const match of value.matchAll(CSS_URL_RE)) {
    const reference = (match[1] ?? match[2] ?? match[3] ?? '').trim()
    if (!isFragmentReference(reference)) return true
  }
  return false
}

/**
 * Validate source safety and structural bounds without rendering or calling a
 * model. Fragment references such as url(#gradient) are allowed; all other
 * href/src and CSS url() references are rejected so the asset is standalone.
 */
export function validateSvgSource(svg, options = {}) {
  const policy = resolvePolicy(options)
  const errors = []
  const warnings = []
  if (typeof svg !== 'string' || svg.length === 0) {
    return { ok: false, errors: ['empty_svg'], warnings, metrics: null }
  }
  if (svg.length > policy.maxChars) {
    errors.push('svg_too_large:' + svg.length + '>' + policy.maxChars)
  }
  if (DOCTYPE_RE.test(svg)) errors.push('doctype_or_entity_declared')

  let doc
  if (errors.length === 0) {
    try {
      const parsed = (options.parser ?? parser()).parseFromString(svg, 'image/svg+xml')
      doc = parsed.doc ?? parsed
      for (const message of parsed.errors ?? []) {
        errors.push('xml_parse:' + message)
      }
    } catch (error) {
      errors.push('xml_parse_fatal:' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const metrics = {
    chars: svg.length,
    elementCount: 0,
    textLabels: 0,
    hasViewBox: false,
    hasText: false,
    dimensions: null,
    safe: true,
  }
  if (!doc?.documentElement) {
    errors.push('xml_not_well_formed')
    return { ok: false, errors, warnings, metrics }
  }

  const root = doc.documentElement
  const rootTag = String(root.tagName ?? '').toLowerCase()
  if (rootTag !== 'svg') {
    errors.push('root_not_svg:' + rootTag)
    return { ok: false, errors, warnings, metrics }
  }
  if (!root.getAttribute('xmlns')) warnings.push('no_svg_namespace')

  if (root.hasAttribute('viewBox')) {
    metrics.hasViewBox = true
    const parts = root.getAttribute('viewBox').trim().split(/[\s,]+/).map(Number)
    if (
      parts.length === 4
      && parts.every(Number.isFinite)
      && parts[2] > 0
      && parts[3] > 0
      && parts[2] <= 10_000
      && parts[3] <= 10_000
    ) {
      metrics.dimensions = { width: parts[2], height: parts[3] }
    } else {
      warnings.push('viewBox_implausible')
    }
  } else if (!root.hasAttribute('width') && !root.hasAttribute('height')) {
    warnings.push('no_viewBox_or_dimensions')
  }

  const unsafe = []
  const walk = node => {
    metrics.elementCount += 1
    const tag = String(node.tagName ?? '').toLowerCase()
    if (UNSAFE_TAGS.has(tag)) unsafe.push('unsafe_tag:' + tag)
    for (const attribute of Array.from(node.attributes ?? [])) {
      const name = attribute.name.toLowerCase()
      const value = attribute.value ?? ''
      if (name.startsWith('on')) {
        unsafe.push('event_handler:' + name)
      } else if (name === 'href' || name === 'src' || name === 'xlink:href') {
        if (!isFragmentReference(value)) unsafe.push('unsafe_reference:' + name)
      } else if (hasUnsafeCssReference(value)) {
        unsafe.push('unsafe_css_reference:' + name)
      }
    }
    if (tag === 'style') {
      const css = node.textContent ?? ''
      if (STYLE_IMPORT_RE.test(css) || hasUnsafeCssReference(css)) {
        unsafe.push('style_external_reference')
      }
    }
    if (tag === 'text' && (node.textContent ?? '').trim().length > 0) {
      metrics.hasText = true
      metrics.textLabels += 1
    }
    for (const child of Array.from(node.childNodes ?? [])) {
      if (child.nodeType === 1) walk(child)
    }
  }
  walk(root)

  if (metrics.elementCount > policy.maxElements) {
    errors.push('too_many_elements:' + metrics.elementCount + '>' + policy.maxElements)
  }
  if (metrics.elementCount < 2) errors.push('svg_empty_no_content')
  if (unsafe.length > 0) {
    metrics.safe = false
    errors.push(...unsafe)
  }
  return { ok: errors.length === 0, errors, warnings, metrics }
}

/**
 * Produce an explainable, deterministic baseline score from validation
 * metrics. It is not a semantic or aesthetic model judgment.
 */
export function scoreSvg(metrics, options = {}) {
  const policy = resolvePolicy(options)
  if (!metrics) return { score: 0, label: 'poor', signals: ['no_metrics'] }

  const signals = ['well_formed']
  let score = 30
  if (metrics.safe) {
    score += 15
    signals.push('no_unsafe_constructs')
  } else {
    signals.push('unsafe_constructs')
  }
  if (metrics.hasViewBox) {
    score += 10
    signals.push('has_viewBox')
  } else {
    score -= 10
    signals.push('no_viewBox')
  }
  if (metrics.dimensions) {
    score += 10
    signals.push('dimensions_plausible')
  }
  if (metrics.elementCount >= 5 && metrics.elementCount <= 300) {
    score += 15
    signals.push('content_rich')
  } else if (metrics.elementCount >= 2 && metrics.elementCount < 5) {
    score += 5
    signals.push('content_sparse')
  } else if (metrics.elementCount > policy.maxElements) {
    score -= 5
    signals.push('complexity_too_high')
  } else {
    score -= 5
    signals.push('content_too_low')
  }
  if (metrics.hasText) {
    score += 10
    signals.push('has_text_labels')
  } else {
    score -= 5
    signals.push('no_text_labels')
  }
  if (metrics.chars <= 40_000) {
    score += 10
    signals.push('size_ok')
  } else {
    score -= 5
    signals.push('size_large')
  }
  const clamped = Math.max(0, Math.min(100, score))
  return {
    score: clamped,
    label: clamped >= GOOD_SCORE ? 'good' : clamped >= WEAK_SCORE ? 'weak' : 'poor',
    signals,
  }
}

/**
 * Gate an SVG under the common policy. The result is complete enough to show
 * an agent exactly why a submission was accepted or rejected.
 */
export function checkSvg(svg, options = {}) {
  const policy = resolvePolicy(options)
  const validation = validateSvgSource(svg, policy)
  const assessment = validation.ok
    ? scoreSvg(validation.metrics, policy)
    : { score: 0, label: 'poor', signals: ['validation_failed'] }
  const sourceHash = typeof svg === 'string'
    ? createHash('sha256').update(svg, 'utf8').digest('hex')
    : null
  return {
    status: validation.ok && assessment.score >= policy.acceptScore ? 'accepted' : 'rejected',
    accepted: validation.ok && assessment.score >= policy.acceptScore,
    valid: validation.ok,
    source_sha256: sourceHash,
    score: assessment.score,
    label: assessment.label,
    signals: assessment.signals,
    errors: validation.errors,
    warnings: validation.warnings,
    metrics: validation.metrics,
    policy: {
      max_elements: policy.maxElements,
      max_chars: policy.maxChars,
      accept_score: policy.acceptScore,
    },
  }
}

/**
 * Stable default identifier for a source. Callers may use an explicit safe id
 * when a human-readable asset name is more useful.
 */
export function assetIdFor(svg) {
  if (typeof svg !== 'string' || svg.length === 0) {
    throw new TypeError('svg source must be a non-empty string')
  }
  return 'svg-' + createHash('sha256').update(svg, 'utf8').digest('hex').slice(0, 12)
}
