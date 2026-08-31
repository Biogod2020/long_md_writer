#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

import { preflightSvg } from '../svg/preflight.js'
import { renderSvgToPng } from '../svg/renderer.js'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fixtureRoot = path.join(packageRoot, 'test', 'fixtures', 'svg-quality')

function outputDirectory(argv) {
  const index = argv.indexOf('--out')
  return path.resolve(index >= 0 ? argv[index + 1] : path.join(process.cwd(), 'svg-quality-output'))
}

const output = outputDirectory(process.argv.slice(2))
const manifest = JSON.parse(await readFile(path.join(fixtureRoot, 'manifest.json'), 'utf8'))
await mkdir(output, { recursive: true })

const results = []
for (const figure of manifest.figures) {
  const source = await readFile(path.join(fixtureRoot, figure.file), 'utf8')
  const preflight = await preflightSvg(source, {
    required_labels: figure.required_labels,
    design_brief: figure.design_brief,
  })
  const rendered = await renderSvgToPng(source)
  const preview = path.join(output, `${figure.id}.png`)
  if (rendered) await writeFile(preview, rendered.png)
  results.push({
    id: figure.id,
    passed: preflight.passed,
    issues: preflight.issues,
    warnings: preflight.warnings,
    design: preflight.metrics?.design ?? null,
    preview: rendered ? preview : null,
    renderer: rendered?.backend ?? null,
  })
}

const report = {
  schema_version: 1,
  passed: results.every(item => item.passed && item.preview),
  output,
  results,
}
console.log(JSON.stringify(report, null, 2))
if (!report.passed) process.exitCode = 1
