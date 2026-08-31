/**
 * Shared visual-design contract for planned SVG figures.
 *
 * The plan states what the figure must communicate before an agent starts
 * drawing. Deterministic profiles bound common layout failure modes; they do
 * not claim to prove scientific truth or aesthetic quality by themselves.
 */

export const FIGURE_TYPES = Object.freeze([
  'mechanism',
  'process',
  'system',
  'comparison',
  'chart',
  'spatial',
  'timeline',
  'conceptual',
])

export const PUBLICATION_WIDTHS = Object.freeze([
  'single_column',
  'double_column',
])

export const DESIGN_CHECK_KEYS = Object.freeze([
  'visual_hierarchy',
  'text_economy',
  'composition_spacing',
  'publication_legibility',
  'palette_encoding',
  'reading_order',
  'aesthetic_coherence',
])

const FIGURE_TYPE_SET = new Set(FIGURE_TYPES)
const PUBLICATION_WIDTH_SET = new Set(PUBLICATION_WIDTHS)

const PROFILES = Object.freeze({
  mechanism: { maxTextItems: 24, maxTextRunChars: 44, maxFontSizes: 5, minimumContentArea: 0.26, maximumCenterOffset: 0.18 },
  process: { maxTextItems: 22, maxTextRunChars: 40, maxFontSizes: 4, minimumContentArea: 0.22, maximumCenterOffset: 0.16 },
  system: { maxTextItems: 28, maxTextRunChars: 44, maxFontSizes: 5, minimumContentArea: 0.28, maximumCenterOffset: 0.17 },
  comparison: { maxTextItems: 24, maxTextRunChars: 42, maxFontSizes: 5, minimumContentArea: 0.26, maximumCenterOffset: 0.16 },
  chart: { maxTextItems: 22, maxTextRunChars: 36, maxFontSizes: 4, minimumContentArea: 0.32, maximumCenterOffset: 0.15 },
  spatial: { maxTextItems: 22, maxTextRunChars: 40, maxFontSizes: 4, minimumContentArea: 0.26, maximumCenterOffset: 0.18 },
  timeline: { maxTextItems: 22, maxTextRunChars: 40, maxFontSizes: 4, minimumContentArea: 0.22, maximumCenterOffset: 0.15 },
  conceptual: { maxTextItems: 24, maxTextRunChars: 44, maxFontSizes: 5, minimumContentArea: 0.22, maximumCenterOffset: 0.18 },
})

function text(value, name) {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${name} must be non-empty text`)
  const normalized = value.trim()
  if (normalized.length > 800) throw new TypeError(`${name} must contain at most 800 characters`)
  return normalized
}

function stringArray(value, name, { minimum = 1, maximum = 8 } = {}) {
  if (!Array.isArray(value) || value.length < minimum || value.length > maximum) {
    throw new TypeError(`${name} must contain between ${minimum} and ${maximum} entries`)
  }
  const normalized = value.map((item, index) => text(item, `${name}[${index}]`))
  if (new Set(normalized).size !== normalized.length) throw new TypeError(`${name} must contain unique entries`)
  return normalized
}

export function normalizeDesignBrief(value, { purpose = '', strict = true, name = 'design_brief' } = {}) {
  if (value === undefined && !strict) {
    const fallback = text(purpose || 'Communicate the planned visual purpose.', `${name}.scientific_claim`)
    return {
      figure_type: 'conceptual',
      publication_width: 'double_column',
      scientific_claim: fallback,
      scientific_checks: [fallback],
      reading_order: ['Read the visual in its natural spatial order.'],
      legacy_defaulted: true,
    }
  }
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${name} must be an object`)
  }
  const figureType = text(value.figure_type, `${name}.figure_type`)
  if (!FIGURE_TYPE_SET.has(figureType)) {
    throw new TypeError(`${name}.figure_type must be one of ${FIGURE_TYPES.join(', ')}`)
  }
  const publicationWidth = value.publication_width === undefined && !strict
    ? 'double_column'
    : text(value.publication_width, `${name}.publication_width`)
  if (!PUBLICATION_WIDTH_SET.has(publicationWidth)) {
    throw new TypeError(`${name}.publication_width must be one of ${PUBLICATION_WIDTHS.join(', ')}`)
  }
  return {
    figure_type: figureType,
    publication_width: publicationWidth,
    scientific_claim: text(value.scientific_claim, `${name}.scientific_claim`),
    scientific_checks: stringArray(value.scientific_checks, `${name}.scientific_checks`),
    reading_order: stringArray(value.reading_order, `${name}.reading_order`),
    legacy_defaulted: !strict && value.legacy_defaulted === true,
  }
}

export function designProfile(value) {
  const brief = normalizeDesignBrief(value, { strict: false })
  return {
    ...PROFILES[brief.figure_type],
    figureType: brief.figure_type,
    publicationWidth: brief.publication_width,
    // Stored schema-v1 plans carry an explicit internal marker. Preserve it
    // when preflight normalizes the plan again so legacy figures keep the
    // conservative 12 px floor instead of being mistaken for an intentional
    // double-column design brief.
    legacyDefaulted: brief.legacy_defaulted || value?.legacy_defaulted === true,
  }
}
