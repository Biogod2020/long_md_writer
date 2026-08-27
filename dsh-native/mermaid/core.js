/**
 * Deterministic, renderer-independent policy for caller-supplied Mermaid.
 * Actual Mermaid syntax is decided by the pinned local Mermaid renderer; this
 * module bounds the source and rejects constructs that could create active or
 * externally linked SVG output before a browser is started.
 *
 * @module longwriter/mermaid-core
 */

import { createHash } from 'node:crypto'

export const DEFAULT_MAX_CHARS = 40_000
export const DEFAULT_MAX_LINES = 1_000

const DIAGRAM_DECLARATIONS = [
  ['flowchart', /^flowchart\s+(?:TB|TD|BT|RL|LR)\b/iu],
  ['graph', /^graph\s+(?:TB|TD|BT|RL|LR)\b/iu],
  ['sequence', /^sequenceDiagram\b/iu],
  ['class', /^classDiagram(?:-v2)?\b/iu],
  ['state', /^stateDiagram(?:-v2)?\b/iu],
  ['entity-relationship', /^erDiagram\b/iu],
  ['requirement', /^requirementDiagram\b/iu],
  ['journey', /^journey\b/iu],
  ['gantt', /^gantt\b/iu],
  ['pie', /^pie\b/iu],
  ['git', /^gitGraph\b/iu],
  ['mindmap', /^mindmap\b/iu],
  ['timeline', /^timeline\b/iu],
  ['quadrant', /^quadrantChart\b/iu],
  ['xychart', /^xychart-beta\b/iu],
  ['block', /^block-beta\b/iu],
  ['packet', /^packet-beta\b/iu],
  ['architecture', /^architecture-beta\b/iu],
  ['kanban', /^kanban\b/iu],
  ['sankey', /^sankey-beta\b/iu],
  ['c4', /^C4(?:Context|Container|Component|Dynamic|Deployment)\b/u],
]

const DIRECTIVE = /^\s*%%\{/mu
const CLICK_ACTION = /^\s*click\s+/imu
const HTML = /<\s*\/?\s*(?:script|style|iframe|object|embed|foreignObject|img|a)\b/iu
const EXTERNAL_URL = /(?:https?:\/\/|data:|javascript:)/iu
const CONTROL_CHARACTER = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/u

function boundedInteger(value, name, fallback, minimum, maximum) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isInteger(resolved) || resolved < minimum || resolved > maximum) {
    throw new Error(`mermaid policy: ${name} must be an integer in ${minimum}..${maximum}`)
  }
  return resolved
}

export function resolveMermaidPolicy(input = {}) {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('mermaid policy: config must be an object')
  }
  return {
    maxChars: boundedInteger(input.maxChars, 'maxChars', DEFAULT_MAX_CHARS, 100, 500_000),
    maxLines: boundedInteger(input.maxLines, 'maxLines', DEFAULT_MAX_LINES, 2, 10_000),
  }
}

function firstDeclaration(source) {
  const line = source
    .replace(/^\uFEFF/u, '')
    .split(/\r?\n/u)
    .map(item => item.trim())
    .find(item => item.length > 0 && !item.startsWith('%%'))
  if (!line) return null
  for (const [kind, pattern] of DIAGRAM_DECLARATIONS) {
    if (pattern.test(line)) return { kind, declaration: line }
  }
  return { kind: null, declaration: line }
}

/** Check bounded source safety without starting Mermaid or a browser. */
export function checkMermaidSource(source, options = {}) {
  const policy = resolveMermaidPolicy(options)
  const errors = []
  const warnings = []
  if (typeof source !== 'string' || source.trim().length === 0) {
    return {
      accepted: false,
      errors: ['empty_mermaid'],
      warnings,
      metrics: { chars: 0, lines: 0, diagram_type: null },
    }
  }
  const chars = source.length
  const lines = source.split(/\r?\n/u).length
  if (chars > policy.maxChars) errors.push(`mermaid_too_large:${chars}>${policy.maxChars}`)
  if (lines > policy.maxLines) errors.push(`mermaid_too_many_lines:${lines}>${policy.maxLines}`)
  if (CONTROL_CHARACTER.test(source)) errors.push('control_character')
  if (DIRECTIVE.test(source)) errors.push('init_directive_not_allowed')
  if (CLICK_ACTION.test(source)) errors.push('click_action_not_allowed')
  if (HTML.test(source)) errors.push('html_markup_not_allowed')
  if (EXTERNAL_URL.test(source)) errors.push('external_url_not_allowed')

  const declaration = firstDeclaration(source)
  if (!declaration) errors.push('diagram_declaration_missing')
  else if (!declaration.kind) errors.push(`unsupported_diagram_declaration:${declaration.declaration.slice(0, 80)}`)
  if (!/\baccTitle\s*:/iu.test(source)) warnings.push('accessibility_title_missing')
  if (!/\baccDescr\s*:/iu.test(source)) warnings.push('accessibility_description_missing')

  return {
    accepted: errors.length === 0,
    errors,
    warnings,
    metrics: {
      chars,
      lines,
      diagram_type: declaration?.kind ?? null,
    },
  }
}

export function mermaidSourceId(source) {
  if (typeof source !== 'string' || source.length === 0) throw new TypeError('source must be a non-empty string')
  return `mermaid-src-${createHash('sha256').update(source, 'utf8').digest('hex').slice(0, 20)}`
}

export function mermaidAssetId(source) {
  if (typeof source !== 'string' || source.length === 0) throw new TypeError('source must be a non-empty string')
  return `mermaid-${createHash('sha256').update(source, 'utf8').digest('hex').slice(0, 20)}`
}
