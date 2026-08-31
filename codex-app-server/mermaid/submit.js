/** Controlled Mermaid source retention, rendering, and SVG registration. */

import { Buffer } from 'node:buffer'

import { sha256Text } from '../lib/project-store.js'
import { submitSvg } from '../svg/submit.js'
import { checkMermaidSource, mermaidAssetId, mermaidSourceId, resolveMermaidPolicy } from './core.js'
import { MERMAID_CLI_VERSION, renderMermaidToSvg } from './renderer.js'

const SAFE_ID = /^[A-Za-z0-9_-]+$/u

function requiredText(value, name, fallback) {
  const resolved = value === undefined ? fallback : value
  if (typeof resolved !== 'string' || resolved.trim().length === 0) {
    throw new TypeError(`${name} must be a non-empty string`)
  }
  return resolved.trim()
}

function safeId(value, source) {
  const id = value === undefined ? mermaidAssetId(source) : requiredText(value, 'id')
  if (id.length > 100 || !SAFE_ID.test(id)) throw new TypeError('id may contain only letters, digits, "-" and "_"')
  return id
}

function usedIn(value) {
  if (!Array.isArray(value)) throw new TypeError('used_in must be an array of non-empty strings')
  return value.map((item, index) => requiredText(item, `used_in[${index}]`))
}

async function retainSource(workspace, input, dependencies) {
  const sourceId = mermaidSourceId(input.mermaid)
  const sourcePath = `assets/mermaid/${sourceId}.mmd`
  const expectedSha = sha256Text(input.mermaid)
  const manifest = await dependencies.readAssetManifest(workspace)
  const existing = manifest.assets.find(entry => entry?.id === sourceId)
  if (existing) {
    const retained = await dependencies.readRegisteredAsset(workspace, sourceId)
    if (existing.path !== sourcePath || retained.sha256 !== expectedSha || retained.bytes.toString('utf8') !== input.mermaid) {
      throw new Error(`retained Mermaid source does not match its content id: ${sourceId}`)
    }
    return { id: sourceId, path: sourcePath, sha256: expectedSha, reused: true }
  }
  const registered = await dependencies.registerAsset(workspace, {
    id: sourceId,
    source: requiredText(input.source, 'source', 'agent'),
    path: sourcePath,
    caption: `Mermaid source for ${requiredText(input.caption, 'caption')}`,
    alt_text: 'Editable Mermaid source retained for the rendered publication figure.',
    provenance: `agent_generated:mermaid-source@${MERMAID_CLI_VERSION}`,
    licence: requiredText(input.licence, 'licence', 'generated_internal'),
    used_in: input.used_in,
    bytes: Buffer.from(input.mermaid, 'utf8'),
  })
  return { id: sourceId, path: registered.path, sha256: registered.sha256, reused: false }
}

export async function submitMermaid(workspace, input, dependencies = {}) {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('mermaid submission requires an object')
  }
  for (const name of ['registerAsset', 'resolveVisualPlan', 'readAssetManifest', 'readRegisteredAsset']) {
    if (typeof dependencies[name] !== 'function') throw new TypeError(`mermaid submission requires ${name}`)
  }
  const policy = resolveMermaidPolicy(dependencies.policy ?? {})
  const sourceGate = checkMermaidSource(input.mermaid, policy)
  if (!sourceGate.accepted) {
    return { status: 'rejected', registered: false, source_gate: sourceGate }
  }

  const id = safeId(input.id, input.mermaid)
  const plannedUse = usedIn(input.used_in)
  let rendered
  try {
    rendered = await (dependencies.renderMermaid ?? renderMermaidToSvg)(input.mermaid, {
      signal: dependencies.signal,
      timeoutMs: dependencies.timeoutMs,
    })
  } catch (error) {
    return {
      status: 'render_error',
      registered: false,
      source_gate: sourceGate,
      reason: error instanceof Error ? error.message : String(error),
    }
  }

  const common = {
    svg: rendered.svg,
    id,
    caption: input.caption,
    alt_text: input.alt_text,
    visual_plan_id: input.visual_plan_id,
    supersedes_asset_id: input.supersedes_asset_id,
    source: requiredText(input.source, 'source', 'agent'),
    provenance: `agent_generated:${rendered.backend}`,
    licence: requiredText(input.licence, 'licence', 'generated_internal'),
    used_in: plannedUse,
    accept_score: input.accept_score,
  }
  const svgPolicy = { maxChars: 500_000, maxElements: 5_000, acceptScore: input.accept_score ?? 55 }
  const checked = await submitSvg(workspace, { ...common, dry_run: true }, {
    registerAsset: dependencies.registerAsset,
    resolveVisualPlan: dependencies.resolveVisualPlan,
    policy: svgPolicy,
  })
  if (checked.status !== 'checked') {
    return {
      status: checked.status === 'error' ? 'error' : 'rejected',
      registered: false,
      source_gate: sourceGate,
      svg_gate: checked,
      ...(checked.reason ? { reason: checked.reason } : {}),
    }
  }
  if (input.dry_run === true) {
    return {
      status: 'checked',
      registered: false,
      source_gate: sourceGate,
      svg_gate: checked,
      renderer: rendered.backend,
      visual_plan_id: checked.visual_plan_id,
      planned_section_id: checked.planned_section_id,
    }
  }

  try {
    const sourceAsset = await retainSource(workspace, { ...input, used_in: plannedUse }, dependencies)
    const registered = await submitSvg(workspace, {
      ...common,
      derivative_of: {
        asset_id: sourceAsset.id,
        asset_sha256: sourceAsset.sha256,
        purpose: 'rendered_from_mermaid_source',
      },
    }, {
      registerAsset: dependencies.registerAsset,
      resolveVisualPlan: dependencies.resolveVisualPlan,
      policy: svgPolicy,
    })
    return {
      ...registered,
      source_gate: sourceGate,
      renderer: rendered.backend,
      source_asset_id: sourceAsset.id,
      source_asset_path: sourceAsset.path,
      source_asset_sha256: sourceAsset.sha256,
      source_asset_reused: sourceAsset.reused,
    }
  } catch (error) {
    return {
      status: 'error',
      registered: false,
      source_gate: sourceGate,
      renderer: rendered.backend,
      reason: error instanceof Error ? error.message : String(error),
    }
  }
}
