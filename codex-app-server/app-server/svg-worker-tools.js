import { preflightSvg } from '../svg/preflight.js'

export const SVG_PREFLIGHT_CANDIDATE_TOOL_SPEC = {
  type: 'function',
  name: 'svg_preflight_candidate',
  description: 'Run the exact deterministic publication preflight on an initial SVG candidate without registering or writing it. Use the returned element ids and geometry to repair the same candidate, then deliver it.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      svg: { type: 'string', description: 'Complete self-contained initial SVG candidate.' },
    },
    required: ['svg'],
  },
}

export const SVG_PREFLIGHT_DRAFT_TOOL_SPEC = {
  type: 'function',
  name: 'svg_preflight_draft',
  description: 'Run the exact deterministic publication preflight on the current host-held svg_edit draft. This is read-only and never writes the canonical workspace.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    properties: {},
  },
}

function boundedInteger(value, fallback, minimum, maximum, name) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isSafeInteger(resolved) || resolved < minimum || resolved > maximum) {
    throw new TypeError(`${name} must be an integer in ${minimum}..${maximum}`)
  }
  return resolved
}

function compactTargets(metrics = {}) {
  return {
    texts: (metrics.text_boxes ?? []).map(item => ({
      index: item.index,
      id: item.id,
      text: item.text,
      semantic_label: item.semantic_label,
      box: item.box,
      effective_font_size: item.effective_font_size,
      resolved_font_name: item.resolved_font_name,
      missing_characters: item.missing_characters,
    })).slice(0, 48),
    shapes: (metrics.shape_boxes ?? []).map(item => ({
      index: item.index,
      id: item.id,
      tag: item.tag,
      box: item.box,
    })).slice(0, 80),
  }
}

export function compactWorkerPreflight(report, check, maximumChecks) {
  const passed = report.passed === true
  return {
    status: passed ? 'passed' : 'failed',
    passed,
    check,
    remaining_checks: maximumChecks - check,
    source_sha256: report.source_sha256,
    metric_mode: report.metric_mode,
    issue_count: report.issues.length,
    issues: report.issues.slice(0, 32),
    warnings: report.warnings.slice(0, 8),
    required_labels: report.required_labels,
    design_metrics: report.metrics?.design ?? null,
    editable_targets: compactTargets(report.metrics),
    instruction: passed
      ? 'Deterministic preflight passed. Stop checking and emit the required final structured JSON now.'
      : 'Repair the listed id-addressed targets directly. Recheck only after a coherent set of fixes; do not restart the figure.',
  }
}

export class SvgWorkerPreflight {
  constructor(plan, options = {}) {
    if (!plan || typeof plan !== 'object') throw new TypeError('SVG worker preflight requires a visual plan')
    this.plan = plan
    this.maximumChecks = boundedInteger(options.maximumChecks, 3, 1, 8, 'SVG worker maximum preflight checks')
    this.checks = 0
  }

  async inspect(svg) {
    if (this.checks >= this.maximumChecks) {
      throw new Error(`SVG worker preflight budget exhausted at ${this.checks}; deliver the best current candidate now`)
    }
    this.checks += 1
    const report = await preflightSvg(svg, {
      required_labels: this.plan.required_labels,
      design_brief: this.plan.design_brief,
    })
    return compactWorkerPreflight(report, this.checks, this.maximumChecks)
  }
}
