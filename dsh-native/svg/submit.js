/**
 * Controlled SVG submission shared by the DSH tool and portable CLI.
 *
 * A submission is always re-checked immediately before registration. The
 * caller can request dry_run to obtain the same decision without a workspace
 * mutation.
 *
 * @module longwriter/svg-submit
 */

import { Buffer } from 'node:buffer'

import { assetIdFor, checkSvg, resolvePolicy } from './core.js'

const SAFE_ID = /^[A-Za-z0-9_-]+$/

function requiredText(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (typeof resolved !== 'string' || resolved.trim().length === 0) {
    throw new TypeError(name + ' must be a non-empty string')
  }
  return resolved.trim()
}

function safeId(value, svg) {
  const id = value === undefined ? assetIdFor(svg) : requiredText(value, 'id')
  if (id.length > 100 || !SAFE_ID.test(id)) {
    throw new TypeError('id may contain only letters, digits, "-" and "_"')
  }
  return id
}

function usedIn(value) {
  if (value === undefined) return []
  if (!Array.isArray(value)) throw new TypeError('used_in must be an array of non-empty strings')
  return value.map((item, index) => requiredText(item, 'used_in[' + index + ']'))
}

function visualPlanId(value) {
  const id = requiredText(value, 'visual_plan_id')
  if (id.length > 100 || !SAFE_ID.test(id)) {
    throw new TypeError('visual_plan_id may contain only letters, digits, "-" and "_"')
  }
  return id
}

function policyFor(input, basePolicy) {
  const acceptScore = input.accept_score ?? input.acceptScore
  return resolvePolicy({
    ...basePolicy,
    ...(acceptScore === undefined ? {} : { acceptScore }),
  })
}

/**
 * Check and, unless dry_run is set, append a safe SVG asset through the
 * supplied domain store.
 *
 * @param {string} workspace
 * @param {object} input
 * @param {object} dependencies
 * @param {Function} dependencies.registerAsset
 * @param {Function} dependencies.resolveVisualPlan
 * @param {object} [dependencies.policy]
 */
export async function submitSvg(workspace, input, dependencies = {}) {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('svg submission requires an object')
  }
  if (typeof dependencies.registerAsset !== 'function' || typeof dependencies.resolveVisualPlan !== 'function') {
    throw new TypeError('svg submission requires registerAsset and resolveVisualPlan')
  }

  const policy = policyFor(input, dependencies.policy ?? {})
  const gate = checkSvg(input.svg, policy)
  const base = {
    ...gate,
    registered: false,
    asset_id: null,
    asset_path: null,
    asset_sha256: null,
  }
  if (!gate.accepted) return { ...base, status: 'rejected' }

  try {
    const id = safeId(input.id, input.svg)
    const planId = visualPlanId(input.visual_plan_id)
    const supersedesAssetId = input.supersedes_asset_id === undefined
      ? undefined
      : visualPlanId(input.supersedes_asset_id)
    const plan = await dependencies.resolveVisualPlan(workspace, planId)
    const plannedUse = usedIn(input.used_in)
    if (!plan || typeof plan.section_id !== 'string') {
      throw new Error(`visual_plan_id did not resolve to a visual plan: ${planId}`)
    }
    if (!plannedUse.includes(plan.section_id)) {
      throw new Error(`used_in must include the planned section: ${plan.section_id}`)
    }
    if (input.dry_run === true) {
      return { ...base, status: 'checked', visual_plan_id: planId, planned_section_id: plan.section_id }
    }
    const registered = await dependencies.registerAsset(workspace, {
      id,
      source: requiredText(input.source, 'source', 'agent'),
      path: 'assets/svg/' + id + '.svg',
      caption: requiredText(input.caption, 'caption'),
      alt_text: requiredText(input.alt_text, 'alt_text'),
      provenance: requiredText(input.provenance, 'provenance', 'agent_generated:svg-illustrator'),
      licence: requiredText(input.licence, 'licence', 'generated_internal'),
      used_in: plannedUse,
      visual_plan_id: planId,
      ...(supersedesAssetId === undefined ? {} : { supersedes_asset_id: supersedesAssetId }),
      ...(input.derivative_of === undefined ? {} : { derivative_of: input.derivative_of }),
      bytes: Buffer.from(input.svg, 'utf8'),
    })
    return {
      ...base,
      status: 'registered',
      registered: true,
      asset_id: registered.entry.id,
      asset_path: registered.path,
      asset_sha256: registered.sha256,
      visual_plan_id: planId,
      planned_section_id: plan.section_id,
      ...(supersedesAssetId === undefined ? {} : { supersedes_asset_id: supersedesAssetId }),
    }
  } catch (error) {
    return {
      ...base,
      status: 'error',
      reason: error instanceof Error ? error.message : String(error),
    }
  }
}
