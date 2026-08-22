#!/usr/bin/env node

import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { PublicationKernel } from '@longwriter/core'

const HELP = `LongWriter — harness-agnostic publication control plane

Usage:
  longwriter init --workspace DIR --project project.json
  longwriter status --workspace DIR
  longwriter commit --workspace DIR --section ID --chunk ID --file chunk.md [--expected-revision N]
  longwriter revise --workspace DIR --chunk ID --file chunk.md [--expected-revision N]
  longwriter plan-visuals --workspace DIR --contract visual-contract.json [--expected-revision N]
  longwriter validate --workspace DIR
  longwriter review-request --workspace DIR [--focus TEXT]
  longwriter record-review --workspace DIR --input review-bundle.json [--expected-revision N]
  longwriter finalize --workspace DIR [--expected-revision N]
  longwriter svg-check --file figure.svg
  longwriter svg-render --file figure.svg --out figure.png
  longwriter svg-submit --workspace DIR --file figure.svg --visual-plan-id ID --caption TEXT --alt-text TEXT --used-in SECTION
  longwriter svg-preflight --workspace DIR --asset-id ID
  longwriter svg-review --workspace DIR --input visual-review.json

All commands emit JSON. Markdown/SVG commands accept --stdin instead of --file.
`

const REPEATABLE = new Map([
  ['--used-in', 'usedIn'],
  ['--finding', 'findings'],
  ['--checked-label', 'checkedLabels'],
])

const FLAGS = new Map([
  ['--workspace', 'workspace'],
  ['--project', 'project'],
  ['--section', 'section'],
  ['--chunk', 'chunk'],
  ['--file', 'file'],
  ['--contract', 'contract'],
  ['--input', 'input'],
  ['--focus', 'focus'],
  ['--expected-revision', 'expectedRevision'],
  ['--out', 'out'],
  ['--visual-plan-id', 'visualPlanId'],
  ['--supersedes-asset-id', 'supersedesAssetId'],
  ['--asset-id', 'assetId'],
  ['--caption', 'caption'],
  ['--alt-text', 'altText'],
  ['--id', 'id'],
  ['--source', 'source'],
  ['--provenance', 'provenance'],
  ['--licence', 'licence'],
  ['--accept-score', 'acceptScore'],
])

function fail(message) {
  throw new Error(message)
}

function parseArgs(argv) {
  const [command, ...tokens] = argv
  if (!command || command === '--help' || command === '-h' || command === 'help') {
    return { help: true }
  }
  const options = {
    command,
    usedIn: [],
    findings: [],
    checkedLabels: [],
  }
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]
    if (token === '--help' || token === '-h') return { help: true }
    if (token === '--stdin') {
      options.stdin = true
      continue
    }
    if (token === '--overwrite') {
      options.overwrite = true
      continue
    }
    if (token === '--dry-run') {
      options.dryRun = true
      continue
    }
    const repeatable = REPEATABLE.get(token)
    if (repeatable) {
      const value = tokens[++index]
      if (!value) fail(`${token} requires a value`)
      options[repeatable].push(value)
      continue
    }
    const key = FLAGS.get(token)
    if (!key) fail(`unknown option: ${token}`)
    const value = tokens[++index]
    if (!value) fail(`${token} requires a value`)
    options[key] = value
  }
  return options
}

function requireOption(options, key, flag) {
  if (typeof options[key] !== 'string' || options[key].length === 0) {
    fail(`${options.command} requires ${flag}`)
  }
  return options[key]
}

function mutationOptions(options) {
  if (options.expectedRevision === undefined) return {}
  const revision = Number(options.expectedRevision)
  if (!Number.isSafeInteger(revision) || revision < 0) {
    fail('--expected-revision must be a non-negative integer')
  }
  return { expectedRevision: revision }
}

async function readJson(filePath, flag) {
  if (!filePath) fail(`${flag} is required`)
  try {
    return JSON.parse(await readFile(filePath, 'utf8'))
  } catch (error) {
    fail(`cannot read ${flag}: ${error.message}`)
  }
}

async function readStdin() {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

async function sourceFrom(options) {
  if (options.file && options.stdin) fail('use either --file or --stdin, not both')
  if (options.file) return readFile(options.file, 'utf8')
  if (options.stdin) return readStdin()
  fail(`${options.command} requires --file or --stdin`)
}

function kernelFor(options) {
  return new PublicationKernel(requireOption(options, 'workspace', '--workspace'))
}

async function execute(options) {
  if (options.command === 'init') {
    const kernel = kernelFor(options)
    return kernel.initialize(
      await readJson(requireOption(options, 'project', '--project'), '--project'),
      { overwrite: options.overwrite === true },
    )
  }
  if (options.command === 'status') return kernelFor(options).status()
  if (options.command === 'commit') {
    return kernelFor(options).commitChunk({
      section_id: requireOption(options, 'section', '--section'),
      chunk_id: requireOption(options, 'chunk', '--chunk'),
      markdown: await sourceFrom(options),
    }, mutationOptions(options))
  }
  if (options.command === 'revise') {
    return kernelFor(options).reviseChunk({
      chunk_id: requireOption(options, 'chunk', '--chunk'),
      markdown: await sourceFrom(options),
    }, mutationOptions(options))
  }
  if (options.command === 'plan-visuals') {
    return kernelFor(options).planVisuals(
      await readJson(requireOption(options, 'contract', '--contract'), '--contract'),
      mutationOptions(options),
    )
  }
  if (options.command === 'validate') return kernelFor(options).validate()
  if (options.command === 'review-request') {
    return kernelFor(options).createReviewRequest({ focus: options.focus ?? '' })
  }
  if (options.command === 'record-review') {
    const input = await readJson(requireOption(options, 'input', '--input'), '--input')
    return kernelFor(options).recordReview(input, mutationOptions(options))
  }
  if (options.command === 'finalize') {
    return kernelFor(options).finalize(mutationOptions(options))
  }
  if (options.command === 'svg-check') {
    const source = await sourceFrom(options)
    const kernel = new PublicationKernel(process.cwd())
    return kernel.checkSvg(source, options.acceptScore === undefined
      ? {}
      : { acceptScore: Number(options.acceptScore) })
  }
  if (options.command === 'svg-render') {
    const out = requireOption(options, 'out', '--out')
    const kernel = new PublicationKernel(process.cwd())
    const result = await kernel.renderSvg(await sourceFrom(options))
    if (result.status === 'rendered') {
      await writeFile(out, result.png)
      return {
        status: result.status,
        gate: result.gate,
        renderer: result.backend,
        preview_path: path.resolve(out),
      }
    }
    return result
  }
  if (options.command === 'svg-submit') {
    return kernelFor(options).submitSvg({
      svg: await sourceFrom(options),
      id: options.id,
      visual_plan_id: requireOption(options, 'visualPlanId', '--visual-plan-id'),
      supersedes_asset_id: options.supersedesAssetId,
      caption: requireOption(options, 'caption', '--caption'),
      alt_text: requireOption(options, 'altText', '--alt-text'),
      source: options.source,
      provenance: options.provenance,
      licence: options.licence,
      used_in: options.usedIn,
      dry_run: options.dryRun === true,
      accept_score: options.acceptScore === undefined ? undefined : Number(options.acceptScore),
    }, mutationOptions(options))
  }
  if (options.command === 'svg-preflight') {
    return kernelFor(options).preflightSvg({
      asset_id: requireOption(options, 'assetId', '--asset-id'),
    }, mutationOptions(options))
  }
  if (options.command === 'svg-review') {
    const input = await readJson(requireOption(options, 'input', '--input'), '--input')
    return kernelFor(options).recordVisualReview(input, mutationOptions(options))
  }
  fail(`unknown command: ${options.command}`)
}

function output(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`)
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv)
  if (options.help) {
    process.stdout.write(HELP)
    return 0
  }
  const result = await execute(options)
  output(result)
  if (result?.finalized === false || result?.validator?.passed === false || result?.accepted === false) {
    return 2
  }
  return 0
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(
    code => { process.exitCode = code },
    error => {
      process.stderr.write(`${JSON.stringify({
        status: 'error',
        code: error?.code ?? 'LONGWRITER_ERROR',
        message: error instanceof Error ? error.message : String(error),
        current_revision: error?.currentRevision ?? null,
      })}\n`)
      process.exitCode = 1
    },
  )
}
