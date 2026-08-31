/**
 * Narrow SVG domain-tool adapter.
 *
 * The App Server publication runtime supplies the host-specific register
 * function and workspace resolver. This module neither imports Codex packages nor calls
 * a model, so the gate and submission contract remain portable.
 *
 * @module longwriter/svg-domain-adapter
 */

import { checkSvg, resolvePolicy } from './core.js'
import { submitSvg } from './submit.js'
import { preflightAsset } from './workflow.js'

export const name = 'longwriter-svg'

function policyFor(args, policy) {
  return resolvePolicy({
    ...policy,
    ...(args.accept_score === undefined ? {} : { acceptScore: args.accept_score }),
  })
}

function assertDependencies(registerTool, dependencies) {
  if (typeof registerTool !== 'function') throw new TypeError('svg adapter requires registerTool')
  if (typeof dependencies?.workspace !== 'function') throw new TypeError('svg adapter requires workspace resolver')
  if (typeof dependencies?.registerAsset !== 'function') throw new TypeError('svg adapter requires registerAsset')
  if (typeof dependencies?.resolveVisualPlan !== 'function') throw new TypeError('svg adapter requires resolveVisualPlan')
  if (typeof dependencies?.readRegisteredAsset !== 'function') throw new TypeError('svg adapter requires readRegisteredAsset')
  if (typeof dependencies?.readAssetManifest !== 'function') throw new TypeError('svg adapter requires readAssetManifest')
  if (typeof dependencies?.appendVisualPreflight !== 'function') throw new TypeError('svg adapter requires appendVisualPreflight')
}

/**
 * Register model-independent SVG domain tools.
 *
 * @param {Function} registerTool wraps the host tool factory and registry
 * @param {object} dependencies domain-store and workspace functions
 * @param {object} [config] bounded SVG policy only
 */
export function applySvg(registerTool, dependencies, config = {}) {
  assertDependencies(registerTool, dependencies)
  const policy = resolvePolicy(config)

  registerTool({
    name: 'svg_check',
    description: 'Deterministically inspect a caller-supplied SVG before publication. It checks XML structure, standalone safety, element and source bounds, then reports an explainable score. It never writes a file or calls a model.',
    parameters: {
      svg: { type: 'string', required: true, description: 'Complete SVG source to inspect.' },
      accept_score: { type: 'number', description: 'Optional deterministic acceptance threshold from 0 to 100.' },
    },
    isConcurrencySafe: () => true,
    execute(args) {
      return checkSvg(args.svg, policyFor(args, policy))
    },
  })

  registerTool({
    name: 'svg_submit',
    description: 'Re-check a caller-supplied SVG and append it as the canonical assets/svg/<id>.svg candidate bound to an existing visual plan. Requires concise caption, alt_text, visual_plan_id, and the planned section in used_in. A correction after a failed candidate must name that candidate with supersedes_asset_id, creating one append-only revision chain. Set dry_run=true to check the exact submission without writing. This tool does not generate, audit, repair, or model-call the SVG.',
    parameters: {
      svg: { type: 'string', required: true, description: 'Complete SVG source created by the agent.' },
      caption: { type: 'string', description: 'Required for registration: concise publication caption for the asset manifest.' },
      alt_text: { type: 'string', description: 'Required for registration: accessible description of the figure content.' },
      visual_plan_id: { type: 'string', required: true, description: 'Existing project.json visual_contract figure id to bind to this SVG.' },
      supersedes_asset_id: { type: 'string', description: 'Required only for a new SVG revision after an earlier candidate; it must name the current same-plan candidate.' },
      id: { type: 'string', description: 'Optional safe asset id; defaults to a source hash.' },
      source: { type: 'string', description: 'Optional source label; default is agent.' },
      provenance: { type: 'string', description: 'Optional provenance label; default identifies svg-illustrator.' },
      licence: { type: 'string', description: 'Optional licence label; default is generated_internal.' },
      used_in: { type: 'json', description: 'Optional array of non-empty article anchors or section ids.' },
      dry_run: { type: 'boolean', description: 'When true, run the exact gate but do not mutate the workspace.' },
      accept_score: { type: 'number', description: 'Optional deterministic acceptance threshold from 0 to 100.' },
    },
    isConcurrencySafe: () => false,
    async execute(args, exec) {
      if (typeof dependencies.authorizeSvgSubmit === 'function') {
        await dependencies.authorizeSvgSubmit(args, exec)
      }
      return submitSvg(
        dependencies.workspace(exec),
        args,
        {
          registerAsset: dependencies.registerAsset,
          resolveVisualPlan: dependencies.resolveVisualPlan,
          policy: policyFor(args, policy),
        },
      )
    },
  })

  registerTool({
    name: 'svg_preflight',
    description: 'Run deterministic geometry preflight on a registered planned SVG, render a retained assets/reviews/*.png preview, and append a hash-bound receipt. Pass the returned asset_id and preflight_id to inspect_visual. This tool never calls a model.',
    parameters: {
      asset_id: { type: 'string', required: true, description: 'Registered SVG asset id returned by svg_submit.' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return preflightAsset(dependencies.workspace(exec), args, {
        registerAsset: dependencies.registerAsset,
        readRegisteredAsset: dependencies.readRegisteredAsset,
        readAssetManifest: dependencies.readAssetManifest,
        resolveVisualPlan: dependencies.resolveVisualPlan,
        appendVisualPreflight: dependencies.appendVisualPreflight,
        policy,
      })
    },
  })

}
