import { createHash } from 'node:crypto'

import { DOMParser, XMLSerializer } from '@xmldom/xmldom'

import { validateSvgSource } from '../svg/core.js'

const SAFE_TARGET_ID = /^[A-Za-z_][A-Za-z0-9_.:-]{0,99}$/
const SAFE_ATTRIBUTE = /^[A-Za-z_][A-Za-z0-9_.:-]{0,79}$/
const TEXT_TAGS = new Set(['text', 'tspan', 'title', 'desc'])
const FORBIDDEN_ATTRIBUTES = new Set(['id', 'href', 'src', 'xlink:href', 'xmlns'])
const MAX_FRAGMENT_CHARS = 12_000
const MAX_TEXT_CHARS = 2_000
const MAX_ATTRIBUTE_VALUE_CHARS = 2_000
const DEFAULT_MAX_EDITS = 24

export const SVG_EDIT_TOOL_SPEC = {
  type: 'function',
  name: 'svg_edit',
  description: 'Edit the host-held champion SVG draft by stable element id. This is the only allowed revision path; it never writes the canonical workspace. Prefer one atomic operations batch for coordinated local changes; a legacy single operation is also accepted.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      operations: {
        type: 'array',
        description: 'Preferred: 1..16 ordered local DOM operations applied atomically. If any operation fails, none are retained.',
        minItems: 1,
        maxItems: 16,
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            action: { type: 'string', enum: ['set_attributes', 'set_text', 'remove', 'append_fragment'] },
            target_id: { type: 'string' },
            attributes: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                properties: { name: { type: 'string' }, value: { type: 'string' } },
                required: ['name', 'value'],
              },
            },
            text: { type: 'string' },
            fragment: { type: 'string' },
          },
          required: ['action', 'target_id'],
        },
      },
      action: {
        type: 'string',
        enum: ['set_attributes', 'set_text', 'remove', 'append_fragment'],
        description: 'Legacy single-operation form.',
      },
      target_id: { type: 'string', description: 'Stable id of the existing target element.' },
      attributes: {
        type: 'array',
        description: 'For set_attributes, attribute name/value pairs. Existing unmentioned attributes remain unchanged.',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            name: { type: 'string' },
            value: { type: 'string' },
          },
          required: ['name', 'value'],
        },
      },
      text: { type: 'string', description: 'For set_text, replacement text for a text, tspan, title, or desc element.' },
      fragment: { type: 'string', description: 'For append_fragment, a bounded SVG fragment appended below the target container.' },
    },
  },
}

function parseXml(source, label) {
  const errors = []
  const document = new DOMParser({
    onError: (_level, message) => errors.push(String(message)),
  }).parseFromString(source, 'image/svg+xml')
  const parserErrors = Array.from(document.getElementsByTagName('parsererror') ?? [])
  if (errors.length > 0 || parserErrors.length > 0 || !document.documentElement) {
    throw new Error(`${label} is not well-formed XML: ${errors[0] ?? parserErrors[0]?.textContent ?? 'unknown parse error'}`)
  }
  return document
}

function elementChildren(node) {
  return Array.from(node?.childNodes ?? []).filter(child => child.nodeType === 1)
}

function walkElements(root) {
  const elements = []
  const visit = node => {
    elements.push(node)
    for (const child of elementChildren(node)) visit(child)
  }
  visit(root)
  return elements
}

function indexIds(document) {
  const ids = new Map()
  for (const element of walkElements(document.documentElement)) {
    const id = element.getAttribute?.('id')?.trim()
    if (!id) continue
    if (!SAFE_TARGET_ID.test(id)) throw new Error(`SVG contains an unsafe editable id: ${id}`)
    if (ids.has(id)) throw new Error(`SVG contains duplicate editable id: ${id}`)
    ids.set(id, element)
  }
  return ids
}

function requiredTargetId(value) {
  if (typeof value !== 'string' || !SAFE_TARGET_ID.test(value)) {
    throw new TypeError('svg_edit target_id must be a safe existing element id')
  }
  return value
}

function requiredString(value, name, maximum) {
  if (typeof value !== 'string') throw new TypeError(`svg_edit ${name} must be a string`)
  if (value.length > maximum) throw new TypeError(`svg_edit ${name} exceeds ${maximum} characters`)
  return value
}

function normalizedAttributes(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > 24) {
    throw new TypeError('svg_edit attributes must contain 1..24 name/value pairs')
  }
  return value.map((entry, index) => {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new TypeError(`svg_edit attributes[${index}] must be an object`)
    }
    const name = requiredString(entry.name, `attributes[${index}].name`, 80)
    const lower = name.toLowerCase()
    if (!SAFE_ATTRIBUTE.test(name) || lower.startsWith('on') || FORBIDDEN_ATTRIBUTES.has(lower)) {
      throw new TypeError(`svg_edit attribute is not allowed: ${name}`)
    }
    return {
      name,
      value: requiredString(entry.value, `attributes[${index}].value`, MAX_ATTRIBUTE_VALUE_CHARS),
    }
  })
}

function applyOperation(document, args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new TypeError('svg_edit arguments must be an object')
  const targetId = requiredTargetId(args.target_id)
  const ids = indexIds(document)
  const target = ids.get(targetId)
  if (!target) throw new Error(`svg_edit target_id does not exist in the champion draft: ${targetId}`)
  const action = args.action
  if (action === 'set_attributes') {
    const attributes = normalizedAttributes(args.attributes)
    for (const attribute of attributes) target.setAttribute(attribute.name, attribute.value)
    return { targetId, target }
  }
  if (action === 'set_text') {
    const tag = String(target.tagName ?? '').replace(/^.*:/u, '').toLowerCase()
    if (!TEXT_TAGS.has(tag)) throw new Error(`svg_edit set_text cannot target <${tag}>; target a text-bearing element id`)
    target.textContent = requiredString(args.text, 'text', MAX_TEXT_CHARS)
    return { targetId, target }
  }
  if (action === 'remove') {
    if (target === document.documentElement) throw new Error('svg_edit cannot remove the root SVG element')
    target.parentNode.removeChild(target)
    return { targetId, target: null }
  }
  if (action === 'append_fragment') {
    const fragment = requiredString(args.fragment, 'fragment', MAX_FRAGMENT_CHARS)
    if (!fragment.trim()) throw new TypeError('svg_edit fragment must not be empty')
    const wrapper = parseXml(`<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`, 'svg_edit fragment')
    const children = elementChildren(wrapper.documentElement)
    if (children.length === 0 || children.length > 40) {
      throw new Error('svg_edit fragment must contain 1..40 SVG elements')
    }
    for (const child of children) target.appendChild(child.cloneNode(true))
    indexIds(document)
    return { targetId, target }
  }
  throw new TypeError('svg_edit action must be set_attributes, set_text, remove, or append_fragment')
}

function normalizedOperations(args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) {
    throw new TypeError('svg_edit arguments must be an object')
  }
  if (args.operations !== undefined) {
    if (!Array.isArray(args.operations) || args.operations.length < 1 || args.operations.length > 16) {
      throw new TypeError('svg_edit operations must contain 1..16 local operations')
    }
    if (['action', 'target_id', 'attributes', 'text', 'fragment'].some(key => args[key] !== undefined)) {
      throw new TypeError('svg_edit operations cannot be combined with the legacy single-operation fields')
    }
    return args.operations
  }
  return [args]
}

function sha256(source) {
  return createHash('sha256').update(source, 'utf8').digest('hex')
}

export class SvgDraftEditor {
  constructor(source, options = {}) {
    this.source = requiredString(source, 'champion source', 60_000)
    const validation = validateSvgSource(this.source)
    if (!validation.ok) throw new Error(`champion SVG is not editable: ${validation.errors.join(', ')}`)
    indexIds(parseXml(this.source, 'champion SVG'))
    this.revision = 0
    this.maxEdits = options.maxEdits ?? DEFAULT_MAX_EDITS
    if (!Number.isSafeInteger(this.maxEdits) || this.maxEdits < 1 || this.maxEdits > 64) {
      throw new TypeError('svg_edit maxEdits must be an integer in 1..64')
    }
  }

  edit(args) {
    if (this.revision >= this.maxEdits) {
      throw new Error(`svg_edit budget exhausted at revision ${this.revision}; do not call svg_edit again, emit the final structured JSON with edit_revision=${this.revision}`)
    }
    const document = parseXml(this.source, 'champion SVG')
    const operations = normalizedOperations(args)
    const applied = operations.map(operation => applyOperation(document, operation))
    const next = new XMLSerializer().serializeToString(document)
    const validation = validateSvgSource(next)
    if (!validation.ok) {
      throw new Error(`svg_edit rejected the transaction: ${validation.errors.join(', ')}`)
    }
    this.source = next
    this.revision += 1
    const remaining = this.maxEdits - this.revision
    const previews = applied.map((item, index) => ({
      action: operations[index].action,
      target_id: item.targetId,
      target_preview: item.target ? new XMLSerializer().serializeToString(item.target).slice(0, 8_000) : null,
    }))
    return {
      edited: true,
      revision: this.revision,
      source_sha256: sha256(this.source),
      operation_count: operations.length,
      operations: previews,
      action: operations.length === 1 ? operations[0].action : 'batch',
      target_id: operations.length === 1 ? applied[0].targetId : null,
      target_preview: operations.length === 1 ? previews[0].target_preview : null,
      metrics: validation.metrics,
      remaining_edits: remaining,
      instruction: remaining === 0
        ? `Edit budget exhausted. Do not call svg_edit again; emit the final structured JSON with edit_revision=${this.revision}.`
        : 'Continue with another local svg_edit only if necessary; never return a replacement SVG source.',
    }
  }
}
