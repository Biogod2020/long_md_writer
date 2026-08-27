/** Narrow DSH tool adapter for Mermaid -> retained source + controlled SVG. */

import { submitMermaid } from './submit.js'

export const name = 'longwriter-mermaid'

export function applyMermaid(registerTool, dependencies, config = {}) {
  if (typeof registerTool !== 'function') throw new TypeError('mermaid adapter requires registerTool')
  if (typeof dependencies?.workspace !== 'function') throw new TypeError('mermaid adapter requires workspace resolver')
  registerTool({
    name: 'mermaid_submit',
    description: 'Validate caller-supplied Mermaid, render it locally with the pinned Mermaid CLI, retain the editable .mmd source, and register the standalone SVG as a hash-bound derivative of that source under an existing visual plan. Set dry_run=true to render and run the exact SVG gate without writing. After registration, use svg_preflight, inspect its PNG with read_image, and record svg_record_review before citing the returned SVG path.',
    parameters: {
      mermaid: { type: 'string', required: true, description: 'Complete Mermaid definition beginning with a supported diagram declaration.' },
      caption: { type: 'string', required: true, description: 'Concise publication caption.' },
      alt_text: { type: 'string', required: true, description: 'Accessible description of the rendered diagram.' },
      visual_plan_id: { type: 'string', required: true, description: 'Existing project.json visual_contract figure id.' },
      supersedes_asset_id: { type: 'string', description: 'Required for a new revision after an earlier SVG candidate for the same plan.' },
      id: { type: 'string', description: 'Optional safe SVG asset id; defaults to a Mermaid source hash.' },
      source: { type: 'string', description: 'Optional source label; defaults to agent.' },
      licence: { type: 'string', description: 'Optional licence label; defaults to generated_internal.' },
      used_in: { type: 'json', required: true, description: 'Article section ids; must include the visual plan section.' },
      dry_run: { type: 'boolean', description: 'Render and validate without retaining either source or SVG.' },
      accept_score: { type: 'number', description: 'Optional SVG deterministic acceptance threshold from 0 to 100.' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return submitMermaid(dependencies.workspace(exec), args, {
        ...dependencies,
        policy: config,
        signal: exec.signal,
      })
    },
  })
}
