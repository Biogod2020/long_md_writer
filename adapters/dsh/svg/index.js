export function applySvg(registerTool, kernelFromExecution) {
  registerTool({
    name: 'svg_check',
    description: 'Deterministically inspect caller-supplied SVG source without writing files or calling a model.',
    parameters: {
      svg: { type: 'string', required: true, description: 'Complete SVG source.' },
      accept_score: { type: 'number', description: 'Optional acceptance threshold from 0 to 100.' },
    },
    isConcurrencySafe: () => true,
    execute(args, exec) {
      return kernelFromExecution(exec).checkSvg(
        args.svg,
        args.accept_score === undefined ? {} : { acceptScore: args.accept_score },
      )
    },
  })

  registerTool({
    name: 'svg_submit',
    description: 'Check and register a planned SVG through the LongWriter kernel. A dry run does not mutate or advance revision.',
    parameters: {
      svg: { type: 'string', required: true },
      visual_plan_id: { type: 'string', required: true },
      id: { type: 'string' },
      supersedes_asset_id: { type: 'string' },
      caption: { type: 'string', required: true },
      alt_text: { type: 'string', required: true },
      source: { type: 'string' },
      provenance: { type: 'string' },
      licence: { type: 'string' },
      used_in: { type: 'json' },
      dry_run: { type: 'boolean' },
      accept_score: { type: 'number' },
      expected_revision: { type: 'number' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return kernelFromExecution(exec).submitSvg(args, {
        expectedRevision: args.expected_revision,
      })
    },
  })

  registerTool({
    name: 'svg_preflight',
    description: 'Retain a PNG preview and append deterministic geometry evidence for a registered SVG.',
    parameters: {
      asset_id: { type: 'string', required: true },
      expected_revision: { type: 'number' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return kernelFromExecution(exec).preflightSvg(
        { asset_id: args.asset_id },
        { expectedRevision: args.expected_revision },
      )
    },
  })

  registerTool({
    name: 'svg_record_review',
    description: 'Append a hash-bound inspection receipt after the retained PNG preview was actually inspected.',
    parameters: {
      asset_id: { type: 'string', required: true },
      preflight_id: { type: 'string', required: true },
      reviewer: { type: 'string', required: true },
      verdict: { type: 'string', required: true },
      summary: { type: 'string', required: true },
      findings: { type: 'json' },
      checked_labels: { type: 'json' },
      expected_revision: { type: 'number' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return kernelFromExecution(exec).recordVisualReview(args, {
        expectedRevision: args.expected_revision,
      })
    },
  })
}
