/**
 * Deterministic SVG geometry preflight.
 *
 * This module does not generate or repair figures. It extracts basic SVG
 * layout primitives, measures text locally, and records explainable clipping,
 * overlap, font-size, contrast, and required-label findings before a final
 * preview is reviewed by a person or independent reviewer.
 *
 * @module longwriter/svg-preflight
 */

import { DOMParser } from '@xmldom/xmldom'

import { checkSvg, resolvePolicy } from './core.js'
import { measureTextRuns } from './metrics.js'

const IDENTITY = [1, 0, 0, 1, 0, 0]
const EPSILON = 0.01
const NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?(?:px|pt)?$/i

function text(value) {
  return typeof value === 'string' ? value.replace(/\s+/gu, ' ').trim() : ''
}

function number(value, fallback = null) {
  if (typeof value !== 'string') return fallback
  const first = value.trim().split(/[\s,]+/u)[0]
  if (!NUMBER.test(first)) return fallback
  const parsed = Number.parseFloat(first)
  return Number.isFinite(parsed) ? parsed : fallback
}

function styleValue(node, name, inherited) {
  const direct = node.getAttribute?.(name)
  if (direct !== null && direct !== '') return direct
  const style = node.getAttribute?.('style') ?? ''
  for (const declaration of style.split(';')) {
    const [key, ...rest] = declaration.split(':')
    if (key?.trim().toLowerCase() === name && rest.length > 0) return rest.join(':').trim()
  }
  return inherited
}

function multiply(left, right) {
  const [a, b, c, d, e, f] = left
  const [g, h, i, j, k, l] = right
  return [
    a * g + c * h,
    b * g + d * h,
    a * i + c * j,
    b * i + d * j,
    a * k + c * l + e,
    b * k + d * l + f,
  ]
}

function point(matrix, x, y) {
  return { x: matrix[0] * x + matrix[2] * y + matrix[4], y: matrix[1] * x + matrix[3] * y + matrix[5] }
}

function bounds(points) {
  const xs = points.map(item => item.x)
  const ys = points.map(item => item.y)
  return { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) }
}

function transformedBox(box, matrix) {
  return bounds([
    point(matrix, box.left, box.top),
    point(matrix, box.right, box.top),
    point(matrix, box.right, box.bottom),
    point(matrix, box.left, box.bottom),
  ])
}

function area(box) {
  return Math.max(0, box.right - box.left) * Math.max(0, box.bottom - box.top)
}

function intersects(left, right) {
  return left.left < right.right - EPSILON
    && left.right > right.left + EPSILON
    && left.top < right.bottom - EPSILON
    && left.bottom > right.top + EPSILON
}

function contains(outer, inner) {
  return outer.left <= inner.left + EPSILON
    && outer.right >= inner.right - EPSILON
    && outer.top <= inner.top + EPSILON
    && outer.bottom >= inner.bottom - EPSILON
}

function scaleFor(matrix) {
  const horizontal = Math.hypot(matrix[0], matrix[1])
  const vertical = Math.hypot(matrix[2], matrix[3])
  return Math.min(horizontal, vertical)
}

function transforms(value) {
  if (!value || !String(value).trim()) return { matrix: IDENTITY, unsupported: [] }
  const source = String(value).trim()
  const pattern = /([a-zA-Z]+)\s*\(([^)]*)\)/g
  let matrix = IDENTITY
  const unsupported = []
  let cursor = 0
  let matched = false
  for (const match of source.matchAll(pattern)) {
    matched = true
    if (source.slice(cursor, match.index).trim()) unsupported.push('syntax')
    cursor = (match.index ?? 0) + match[0].length
    const kind = match[1].toLowerCase()
    const values = match[2].trim() ? match[2].trim().split(/[\s,]+/u).map(Number) : []
    if (values.some(item => !Number.isFinite(item))) {
      unsupported.push(kind)
      continue
    }
    let next
    if (kind === 'matrix' && values.length === 6) next = values
    else if (kind === 'translate' && (values.length === 1 || values.length === 2)) next = [1, 0, 0, 1, values[0], values[1] ?? 0]
    else if (kind === 'scale' && (values.length === 1 || values.length === 2)) next = [values[0], 0, 0, values[1] ?? values[0], 0, 0]
    else if (kind === 'rotate' && (values.length === 1 || values.length === 3)) {
      const radians = values[0] * Math.PI / 180
      const rotation = [Math.cos(radians), Math.sin(radians), -Math.sin(radians), Math.cos(radians), 0, 0]
      next = values.length === 3
        ? multiply(multiply([1, 0, 0, 1, values[1], values[2]], rotation), [1, 0, 0, 1, -values[1], -values[2]])
        : rotation
    } else {
      unsupported.push(kind)
      continue
    }
    matrix = multiply(matrix, next)
  }
  if (!matched || source.slice(cursor).trim()) unsupported.push('syntax')
  return { matrix, unsupported }
}

function parseViewBox(root) {
  const raw = root.getAttribute?.('viewBox')
  const values = raw ? raw.trim().split(/[\s,]+/u).map(Number) : []
  if (values.length === 4 && values.every(Number.isFinite) && values[2] > 0 && values[3] > 0) {
    return { left: values[0], top: values[1], right: values[0] + values[2], bottom: values[1] + values[3] }
  }
  const width = number(root.getAttribute?.('width'))
  const height = number(root.getAttribute?.('height'))
  if (width && height && width > 0 && height > 0) return { left: 0, top: 0, right: width, bottom: height }
  return null
}

function localShapeBox(tag, node) {
  if (tag === 'rect') {
    const x = number(node.getAttribute('x'), 0)
    const y = number(node.getAttribute('y'), 0)
    const width = number(node.getAttribute('width'))
    const height = number(node.getAttribute('height'))
    if (!(width >= 0 && height >= 0)) return null
    return { left: x, top: y, right: x + width, bottom: y + height }
  }
  if (tag === 'circle') {
    const cx = number(node.getAttribute('cx'), 0)
    const cy = number(node.getAttribute('cy'), 0)
    const radius = number(node.getAttribute('r'))
    if (!(radius >= 0)) return null
    return { left: cx - radius, top: cy - radius, right: cx + radius, bottom: cy + radius }
  }
  if (tag === 'ellipse') {
    const cx = number(node.getAttribute('cx'), 0)
    const cy = number(node.getAttribute('cy'), 0)
    const rx = number(node.getAttribute('rx'))
    const ry = number(node.getAttribute('ry'))
    if (!(rx >= 0 && ry >= 0)) return null
    return { left: cx - rx, top: cy - ry, right: cx + rx, bottom: cy + ry }
  }
  if (tag === 'line') {
    const x1 = number(node.getAttribute('x1'), 0)
    const y1 = number(node.getAttribute('y1'), 0)
    const x2 = number(node.getAttribute('x2'), 0)
    const y2 = number(node.getAttribute('y2'), 0)
    return { left: Math.min(x1, x2), top: Math.min(y1, y2), right: Math.max(x1, x2), bottom: Math.max(y1, y2) }
  }
  if (tag === 'polyline' || tag === 'polygon') {
    const values = String(node.getAttribute('points') ?? '').trim().split(/[\s,]+/u).filter(Boolean).map(Number)
    if (values.length < 4 || values.length % 2 || values.some(value => !Number.isFinite(value))) return null
    const points = []
    for (let index = 0; index < values.length; index += 2) points.push({ x: values[index], y: values[index + 1] })
    return bounds(points)
  }
  return undefined
}

function color(value) {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase()
  if (!normalized || normalized === 'none' || normalized === 'transparent') return null
  const named = { black: [0, 0, 0], white: [255, 255, 255], gray: [128, 128, 128], grey: [128, 128, 128] }
  if (named[normalized]) return named[normalized]
  if (/^#[0-9a-f]{3}$/i.test(normalized)) return normalized.slice(1).split('').map(item => Number.parseInt(item + item, 16))
  if (/^#[0-9a-f]{6}$/i.test(normalized)) return [0, 2, 4].map(offset => Number.parseInt(normalized.slice(1 + offset, 3 + offset), 16))
  const rgb = normalized.match(/^rgb\(\s*([\d.]+)(%)?\s*,\s*([\d.]+)(%)?\s*,\s*([\d.]+)(%)?\s*\)$/i)
  if (rgb) {
    return [[rgb[1], rgb[2]], [rgb[3], rgb[4]], [rgb[5], rgb[6]]].map(([value, percent]) => (
      Math.max(0, Math.min(255, Number(value) * (percent ? 2.55 : 1)))
    ))
  }
  return null
}

function luminance(rgb) {
  return rgb.map(channel => {
    const value = channel / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
}

function contrast(left, right) {
  const [low, high] = [luminance(left), luminance(right)].sort((a, b) => a - b)
  return (high + 0.05) / (low + 0.05)
}

function issue(target, value) {
  if (!target.includes(value)) target.push(value)
}

function visibleWithin(box, viewport) {
  return box.left >= viewport.left - EPSILON
    && box.top >= viewport.top - EPSILON
    && box.right <= viewport.right + EPSILON
    && box.bottom <= viewport.bottom + EPSILON
}

function collectLayout(doc) {
  const root = doc.documentElement
  const issues = []
  const warnings = []
  const texts = []
  const shapes = []
  const viewport = parseViewBox(root)
  if (!viewport) issue(issues, 'preflight_requires_viewbox_or_dimensions')

  const walk = (node, inherited) => {
    if (node.nodeType !== 1) return
    const tag = String(node.tagName ?? '').replace(/^.*:/u, '').toLowerCase()
    const parsed = transforms(node.getAttribute?.('transform'))
    for (const unsupported of parsed.unsupported) issue(issues, `unsupported_transform:${unsupported}`)
    const state = {
      matrix: multiply(inherited.matrix, parsed.matrix),
      fontSize: number(styleValue(node, 'font-size', inherited.fontSize), inherited.fontSize),
      fontFamily: styleValue(node, 'font-family', inherited.fontFamily),
      fill: styleValue(node, 'fill', inherited.fill),
      allowOverlap: inherited.allowOverlap || node.getAttribute?.('data-allow-overlap') === 'true',
    }
    if (!(state.fontSize > 0)) {
      issue(issues, 'invalid_font_size')
      state.fontSize = 16
    }
    if (tag === 'text') {
      const content = text(node.textContent)
      if (content) {
        const x = number(node.getAttribute('x'), 0)
        const y = number(node.getAttribute('y'), 0)
        const anchor = String(styleValue(node, 'text-anchor', 'start')).trim().toLowerCase()
        if (!['start', 'middle', 'end'].includes(anchor)) issue(warnings, `text_anchor_defaulted:${texts.length}`)
        texts.push({
          index: texts.length,
          text: content,
          x,
          y,
          anchor: ['start', 'middle', 'end'].includes(anchor) ? anchor : 'start',
          font_size: state.fontSize,
          font_family: state.fontFamily,
          fill: state.fill,
          matrix: state.matrix,
          allow_overlap: state.allowOverlap,
        })
      }
    } else {
      const local = localShapeBox(tag, node)
      if (local === undefined && tag === 'path') issue(warnings, 'geometry_path_unchecked')
      if (local === null) issue(issues, `shape_geometry_unparseable:${tag}`)
      if (local) {
        shapes.push({
          index: shapes.length,
          tag,
          box: transformedBox(local, state.matrix),
          fill: state.fill,
          allow_overlap: state.allowOverlap,
        })
      }
    }
    if (tag === 'tspan' && (node.hasAttribute('x') || node.hasAttribute('y') || node.hasAttribute('dx') || node.hasAttribute('dy'))) {
      issue(warnings, 'tspan_layout_approximated')
    }
    for (const child of Array.from(node.childNodes ?? [])) walk(child, state)
  }
  walk(root, { matrix: IDENTITY, fontSize: 16, fontFamily: 'Helvetica', fill: '#000000', allowOverlap: false })
  return { viewport, texts, shapes, issues, warnings }
}

function backgroundFor(textBox, shapes) {
  const center = { x: (textBox.left + textBox.right) / 2, y: (textBox.top + textBox.bottom) / 2 }
  const enclosing = shapes
    .filter(shape => color(shape.fill) && contains(shape.box, { left: center.x, right: center.x, top: center.y, bottom: center.y }))
    .sort((left, right) => area(left.box) - area(right.box))
  return color(enclosing[0]?.fill) ?? [255, 255, 255]
}

function cleanRequiredLabels(value) {
  if (!Array.isArray(value)) throw new TypeError('required_labels must be an array')
  return value.map((label, index) => {
    const normalized = text(label)
    if (!normalized) throw new TypeError(`required_labels[${index}] must be non-empty text`)
    return normalized
  })
}

/**
 * Run deterministic layout checks. `metricOptions.runner` is only a local
 * test seam; production calls the CoreText helper when running on macOS.
 */
export async function preflightSvg(svg, options = {}) {
  const policy = resolvePolicy(options.policy ?? {})
  const gate = checkSvg(svg, policy)
  const issues = []
  const warnings = []
  if (!gate.accepted) issue(issues, 'svg_gate_rejected')
  for (const error of gate.errors) issue(issues, `svg_gate:${error}`)
  for (const warning of gate.warnings) issue(warnings, `svg_gate:${warning}`)

  let doc
  try {
    doc = new DOMParser().parseFromString(svg, 'image/svg+xml')
  } catch (error) {
    issue(issues, `xml_parse:${error instanceof Error ? error.message : String(error)}`)
  }
  if (!doc?.documentElement || String(doc.documentElement.tagName ?? '').toLowerCase() !== 'svg') {
    issue(issues, 'xml_not_svg')
    return {
      status: 'failed', passed: false, source_sha256: gate.source_sha256, metric_mode: 'unavailable',
      issues, warnings, labels: [], required_labels: [], metrics: null,
    }
  }

  const layout = collectLayout(doc)
  for (const value of layout.issues) issue(issues, value)
  for (const value of layout.warnings) issue(warnings, value)
  const requiredLabels = cleanRequiredLabels(options.required_labels ?? [])
  const measured = await measureTextRuns(layout.texts.map(item => ({
    text: item.text,
    font_size: item.font_size,
    font_family: item.font_family,
  })), options.metricOptions ?? {})
  for (const warning of measured.warnings) issue(warnings, warning)

  const renderedTexts = layout.texts.map((item, index) => {
    const metric = measured.measurements[index]
    let left = item.x
    if (item.anchor === 'middle') left -= metric.width / 2
    if (item.anchor === 'end') left -= metric.width
    const local = { left, top: item.y - metric.ascent, right: left + metric.width, bottom: item.y + metric.descent }
    const box = transformedBox(local, item.matrix)
    const effectiveFontSize = item.font_size * scaleFor(item.matrix)
    return { ...item, metric, box, effective_font_size: effectiveFontSize }
  })

  for (const shape of layout.shapes) {
    if (layout.viewport && !visibleWithin(shape.box, layout.viewport)) issue(issues, `shape_outside_viewbox:${shape.index}`)
  }
  for (const item of renderedTexts) {
    if (layout.viewport && !visibleWithin(item.box, layout.viewport)) issue(issues, `text_outside_viewbox:${item.index}`)
    if (item.effective_font_size < 12) issue(issues, `text_below_minimum_font_size:${item.index}`)
    const foreground = color(item.fill)
    if (!foreground) {
      issue(warnings, `text_contrast_unchecked:${item.index}`)
    } else {
      const ratio = contrast(foreground, backgroundFor(item.box, layout.shapes))
      const minimum = item.effective_font_size >= 24 ? 3 : 4.5
      if (ratio + EPSILON < minimum) issue(issues, `text_contrast_below_${minimum}:${item.index}`)
    }
  }

  for (let left = 0; left < renderedTexts.length; left += 1) {
    for (let right = left + 1; right < renderedTexts.length; right += 1) {
      if (!renderedTexts[left].allow_overlap && !renderedTexts[right].allow_overlap && intersects(renderedTexts[left].box, renderedTexts[right].box)) {
        issue(issues, `text_overlap:${left}:${right}`)
      }
    }
  }
  const rectangles = layout.shapes.filter(item => item.tag === 'rect')
  for (let left = 0; left < rectangles.length; left += 1) {
    for (let right = left + 1; right < rectangles.length; right += 1) {
      const first = rectangles[left]
      const second = rectangles[right]
      if (!first.allow_overlap && !second.allow_overlap && intersects(first.box, second.box) && !contains(first.box, second.box) && !contains(second.box, first.box)) {
        issue(issues, `rect_overlap:${first.index}:${second.index}`)
      }
    }
  }
  for (const item of renderedTexts) {
    for (const shape of layout.shapes) {
      if (item.allow_overlap || shape.allow_overlap || !intersects(item.box, shape.box) || contains(shape.box, item.box)) continue
      if (['rect', 'circle', 'ellipse'].includes(shape.tag)) issue(issues, `text_shape_overlap:${item.index}:${shape.index}`)
    }
  }

  const labels = renderedTexts.map(item => item.text)
  const labelStatus = requiredLabels.map(label => ({ label, present: labels.includes(label) }))
  for (const item of labelStatus) {
    if (!item.present) issue(issues, `required_label_missing:${item.label}`)
  }

  return {
    status: issues.length === 0 ? 'passed' : 'failed',
    passed: issues.length === 0,
    source_sha256: gate.source_sha256,
    metric_mode: measured.metric_mode,
    issues,
    warnings,
    labels,
    required_labels: labelStatus,
    metrics: {
      viewport: layout.viewport,
      text_count: renderedTexts.length,
      shape_count: layout.shapes.length,
      text_boxes: renderedTexts.map(item => ({
        index: item.index,
        text: item.text,
        box: item.box,
        effective_font_size: Number(item.effective_font_size.toFixed(3)),
      })),
    },
  }
}
