/**
 * Controlled visual-evidence workflow shared by DSH and the portable CLI.
 *
 * It turns an already registered SVG into an append-only PNG preview plus a
 * hash-bound geometry receipt. A separate explicit review receipt records
 * who inspected that retained preview. No function in this module calls a
 * model or writes outside the supplied domain-store functions.
 *
 * @module longwriter/svg-workflow
 */

import { createHash } from 'node:crypto'

import { preflightSvg } from './preflight.js'
import { renderSvgToPng } from './renderer.js'

const SAFE_ID = /^[A-Za-z0-9_-]+$/

function safeId(value, name) {
  if (typeof value !== 'string' || !SAFE_ID.test(value) || value.length > 100) {
    throw new TypeError(`${name} must be a safe identifier`)
  }
  return value
}

function requireDependency(dependencies, name) {
  if (typeof dependencies?.[name] !== 'function') throw new TypeError(`visual workflow requires ${name}`)
  return dependencies[name]
}

export function previewAssetIdFor(assetId, assetSha256) {
  const digest = createHash('sha256').update(`${assetId}:${assetSha256}`, 'utf8').digest('hex').slice(0, 20)
  return `preview-${digest}`
}

function reusablePreview(manifest, asset) {
  return manifest.assets.find(entry => entry
    && entry.derivative_of
    && entry.derivative_of.asset_id === asset.entry.id
    && entry.derivative_of.asset_sha256 === asset.sha256
    && entry.derivative_of.purpose === 'svg-preview') ?? null
}

/**
 * Render and retain a reviewable preview, then append a geometry-preflight
 * receipt that binds the SVG, preview, plan, and both hashes together.
 */
export async function preflightAsset(workspace, input, dependencies = {}) {
  try {
    const readRegisteredAsset = requireDependency(dependencies, 'readRegisteredAsset')
    const readAssetManifest = requireDependency(dependencies, 'readAssetManifest')
    const resolveVisualPlan = requireDependency(dependencies, 'resolveVisualPlan')
    const registerAsset = requireDependency(dependencies, 'registerAsset')
    const appendVisualPreflight = requireDependency(dependencies, 'appendVisualPreflight')
    const assetId = safeId(input?.asset_id, 'asset_id')
    const asset = await readRegisteredAsset(workspace, assetId)
    if (!asset.entry.path.startsWith('assets/svg/') || !asset.entry.path.endsWith('.svg')) {
      throw new Error('svg_preflight requires a registered assets/svg/*.svg asset')
    }
    const planId = safeId(asset.entry.visual_plan_id, 'registered asset visual_plan_id')
    const plan = await resolveVisualPlan(workspace, planId)
    const svg = Buffer.from(asset.bytes).toString('utf8')
    const report = await preflightSvg(svg, {
      policy: dependencies.policy,
      required_labels: plan.required_labels,
      metricOptions: dependencies.metricOptions,
    })
    if (report.source_sha256 !== asset.sha256) {
      throw new Error('registered SVG bytes are not valid UTF-8 source for hash-bound preflight')
    }
    const renderer = dependencies.renderSvgToPng ?? renderSvgToPng
    const rendered = await renderer(svg)
    if (!rendered) {
      return { status: 'error', reason: 'no_svg_renderer_available', report, visual_plan_id: plan.id }
    }

    let preview = reusablePreview(await readAssetManifest(workspace), asset)
    if (preview) {
      const verified = await readRegisteredAsset(workspace, preview.id)
      preview = { ...preview, sha256: verified.sha256, path: verified.path }
    } else {
      const previewId = previewAssetIdFor(asset.entry.id, asset.sha256)
      const registered = await registerAsset(workspace, {
        id: previewId,
        source: 'tool',
        path: `assets/reviews/${previewId}.png`,
        caption: `Deterministic PNG preview for ${asset.entry.caption}`,
        alt_text: `Review preview rendered from SVG asset ${asset.entry.id}.`,
        provenance: 'derived:svg-preflight',
        licence: asset.entry.licence,
        used_in: [],
        derivative_of: {
          asset_id: asset.entry.id,
          asset_sha256: asset.sha256,
          purpose: 'svg-preview',
        },
        bytes: rendered.png,
      })
      preview = { ...registered.entry, sha256: registered.sha256, path: registered.path }
    }
    const receipt = await appendVisualPreflight(workspace, {
      asset_id: asset.entry.id,
      asset_sha256: asset.sha256,
      visual_plan_id: plan.id,
      preview_asset_id: preview.id,
      preview_sha256: preview.sha256,
      metric_mode: report.metric_mode,
      renderer: rendered.backend,
      passed: report.passed,
      issues: report.issues,
      warnings: report.warnings,
    })
    return {
      status: report.passed ? 'passed' : 'failed',
      visual_plan_id: plan.id,
      planned_section_id: plan.section_id,
      asset_id: asset.entry.id,
      asset_sha256: asset.sha256,
      preview_asset_id: preview.id,
      preview_asset_path: preview.path,
      preview_sha256: preview.sha256,
      preflight_id: receipt.id,
      report,
    }
  } catch (error) {
    return { status: 'error', reason: error instanceof Error ? error.message : String(error) }
  }
}

/** Append an explicit inspection record through the hash-validating store. */
export async function recordAssetReview(workspace, input, dependencies = {}) {
  try {
    const appendVisualReview = requireDependency(dependencies, 'appendVisualReview')
    const assetId = safeId(input?.asset_id, 'asset_id')
    const preflightId = safeId(input?.preflight_id, 'preflight_id')
    const receipt = await appendVisualReview(workspace, {
      asset_id: assetId,
      preflight_id: preflightId,
      reviewer: input?.reviewer,
      verdict: input?.verdict,
      summary: input?.summary,
      findings: input?.findings,
      checked_labels: input?.checked_labels,
    })
    return { status: receipt.verdict === 'pass' ? 'recorded_pass' : 'recorded_fail', receipt }
  } catch (error) {
    return { status: 'error', reason: error instanceof Error ? error.message : String(error) }
  }
}
