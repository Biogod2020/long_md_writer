#!/usr/bin/env node
/**
 * Portable SVG gate CLI.
 *
 * Commands:
 *   check  --file figure.svg [--accept-score 55]
 *   render --file figure.svg --out /tmp/figure.png
 *   submit --workspace /path/to/workspace --file figure.svg --visual-plan-id figure-id --caption "..." --alt-text "..."
 */

import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { checkSvg, resolvePolicy } from './core.js'
import { renderSvgToPng } from './renderer.js'
import { submitSvg } from './submit.js'
import { preflightAsset, recordAssetReview } from './workflow.js'
import {
  appendVisualPreflight,
  appendVisualReview,
  readAssetManifest,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
  setVisualContract,
} from '../lib/project-store.js'

const HELP = [
  'Usage: longwriter-svg <check|render|plan|submit|preflight|review> [options]',
  '',
  'check:  --file FILE or stdin; prints the deterministic gate result.',
  'render: --file FILE or stdin --out PNG; writes a noncanonical PNG preview.',
  'plan:   --workspace DIR --contract visual-contract.json; updates only project.json.visual_contract.',
  'submit: --workspace DIR --file FILE or stdin --visual-plan-id ID --caption TEXT --alt-text TEXT;',
  '        re-checks and registers the planned canonical SVG through the domain store.',
  'preflight: --workspace DIR --asset-id ID; retains a PNG preview and geometry receipt.',
  'review: --workspace DIR --asset-id ID --preflight-id ID --reviewer TEXT --verdict pass|fail --summary TEXT;',
  '        records inspection evidence; --checked-label VALUE is repeatable.',
  '',
  'Shared options: --accept-score N --max-elements N --max-chars N',
  'Submit options: --id ID --supersedes-asset-id ID --source TEXT --provenance TEXT --licence TEXT',
  '                --used-in VALUE (repeatable) --dry-run',
  'Review options: --finding VALUE (repeatable) --checked-label VALUE (repeatable)',
].join('\n')

function fail(message) {
  throw new Error(message)
}

function parseOptions(argv) {
  const [command, ...tokens] = argv
  if (!command || command === '--help' || command === '-h') return { help: true }
  const options = { command, usedIn: [], findings: [], checkedLabels: [] }
  const valueFlags = new Map([
    ['--file', 'file'],
    ['--out', 'out'],
    ['--workspace', 'workspace'],
    ['--contract', 'contract'],
    ['--caption', 'caption'],
    ['--alt-text', 'altText'],
    ['--id', 'id'],
    ['--visual-plan-id', 'visualPlanId'],
    ['--supersedes-asset-id', 'supersedesAssetId'],
    ['--asset-id', 'assetId'],
    ['--preflight-id', 'preflightId'],
    ['--reviewer', 'reviewer'],
    ['--verdict', 'verdict'],
    ['--summary', 'summary'],
    ['--source', 'source'],
    ['--provenance', 'provenance'],
    ['--licence', 'licence'],
    ['--accept-score', 'acceptScore'],
    ['--max-elements', 'maxElements'],
    ['--max-chars', 'maxChars'],
  ])
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]
    if (token === '--help' || token === '-h') return { help: true }
    if (token === '--stdin') {
      options.stdin = true
      continue
    }
    if (token === '--dry-run') {
      options.dryRun = true
      continue
    }
    if (token === '--used-in') {
      const value = tokens[++index]
      if (!value) fail('--used-in requires a value')
      options.usedIn.push(value)
      continue
    }
    if (token === '--finding') {
      const value = tokens[++index]
      if (!value) fail('--finding requires a value')
      options.findings.push(value)
      continue
    }
    if (token === '--checked-label') {
      const value = tokens[++index]
      if (!value) fail('--checked-label requires a value')
      options.checkedLabels.push(value)
      continue
    }
    const key = valueFlags.get(token)
    if (!key) fail('unknown option: ' + token)
    const value = tokens[++index]
    if (!value) fail(token + ' requires a value')
    options[key] = value
  }
  return options
}

function policyFrom(options) {
  const number = (value, name) => {
    if (value === undefined) return undefined
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) fail(name + ' must be numeric')
    return parsed
  }
  return resolvePolicy({
    acceptScore: number(options.acceptScore, '--accept-score'),
    maxElements: number(options.maxElements, '--max-elements'),
    maxChars: number(options.maxChars, '--max-chars'),
  })
}

async function readStdin() {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

async function sourceFrom(options) {
  if (options.file && options.stdin) fail('use either --file or --stdin, not both')
  if (options.file) return readFile(options.file, 'utf8')
  return readStdin()
}

function print(value) {
  process.stdout.write(JSON.stringify(value, null, 2) + '\n')
}

async function runCheck(options) {
  const result = checkSvg(await sourceFrom(options), policyFrom(options))
  print(result)
  return result.accepted ? 0 : 2
}

async function runRender(options) {
  if (!options.out) fail('render requires --out PNG')
  const source = await sourceFrom(options)
  const gate = checkSvg(source, policyFrom(options))
  if (!gate.valid) {
    print(gate)
    return 2
  }
  const rendered = await renderSvgToPng(source)
  if (!rendered) {
    print({ ...gate, status: 'error', reason: 'no_svg_renderer_available' })
    return 1
  }
  await writeFile(options.out, rendered.png)
  print({
    ...gate,
    status: 'rendered',
    preview_path: path.resolve(options.out),
    renderer: rendered.backend,
  })
  return 0
}

async function runSubmit(options) {
  if (!options.workspace) fail('submit requires --workspace DIR')
  const result = await submitSvg(options.workspace, {
    svg: await sourceFrom(options),
    id: options.id,
    visual_plan_id: options.visualPlanId,
    supersedes_asset_id: options.supersedesAssetId,
    caption: options.caption,
    alt_text: options.altText,
    source: options.source,
    provenance: options.provenance,
    licence: options.licence,
    used_in: options.usedIn,
    dry_run: options.dryRun === true,
    accept_score: options.acceptScore === undefined ? undefined : Number(options.acceptScore),
  }, { registerAsset, resolveVisualPlan, policy: policyFrom(options) })
  print(result)
  if (result.status === 'registered' || result.status === 'checked') return 0
  return result.status === 'rejected' ? 2 : 1
}

async function runPlan(options) {
  if (!options.workspace) fail('plan requires --workspace DIR')
  if (!options.contract) fail('plan requires --contract FILE')
  const visualContract = JSON.parse(await readFile(options.contract, 'utf8'))
  const result = await setVisualContract(options.workspace, visualContract)
  print({ status: 'planned', visual_contract: result })
  return 0
}

function workflowDependencies(options) {
  return {
    registerAsset,
    readRegisteredAsset,
    readAssetManifest,
    resolveVisualPlan,
    appendVisualPreflight,
    appendVisualReview,
    policy: policyFrom(options),
  }
}

async function runPreflight(options) {
  if (!options.workspace) fail('preflight requires --workspace DIR')
  if (!options.assetId) fail('preflight requires --asset-id ID')
  const result = await preflightAsset(options.workspace, { asset_id: options.assetId }, workflowDependencies(options))
  print(result)
  if (result.status === 'passed') return 0
  return result.status === 'failed' ? 2 : 1
}

async function runReview(options) {
  if (!options.workspace) fail('review requires --workspace DIR')
  for (const [key, label] of [['assetId', '--asset-id'], ['preflightId', '--preflight-id'], ['reviewer', '--reviewer'], ['verdict', '--verdict'], ['summary', '--summary']]) {
    if (!options[key]) fail(`review requires ${label}`)
  }
  const result = await recordAssetReview(options.workspace, {
    asset_id: options.assetId,
    preflight_id: options.preflightId,
    reviewer: options.reviewer,
    verdict: options.verdict,
    summary: options.summary,
    findings: options.findings,
    checked_labels: options.checkedLabels,
  }, workflowDependencies(options))
  print(result)
  if (result.status === 'recorded_pass') return 0
  return result.status === 'recorded_fail' ? 2 : 1
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseOptions(argv)
  if (options.help) {
    process.stdout.write(HELP + '\n')
    return 0
  }
  if (options.command === 'check') return runCheck(options)
  if (options.command === 'render') return runRender(options)
  if (options.command === 'plan') return runPlan(options)
  if (options.command === 'submit') return runSubmit(options)
  if (options.command === 'preflight') return runPreflight(options)
  if (options.command === 'review') return runReview(options)
  fail('unknown command: ' + options.command)
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(
    code => { process.exitCode = code },
    error => {
      process.stderr.write(JSON.stringify({
        status: 'error',
        reason: error instanceof Error ? error.message : String(error),
      }) + '\n')
      process.exitCode = 1
    },
  )
}
