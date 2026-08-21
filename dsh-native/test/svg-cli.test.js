import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { initializeProject, readAssetManifest, readProject } from '../lib/project-store.js'

const CLI = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../svg/cli.js')
const VALID_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">',
  '<rect width="200" height="100" fill="#fff"/>',
  '<circle cx="50" cy="50" r="20" fill="#268bd2"/>',
  '<line x1="80" y1="50" x2="160" y2="50" stroke="#222"/>',
  '<text x="100" y="90" text-anchor="middle">Flow</text>',
  '</svg>',
].join('\n')

function runCli(args, input = '') {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [CLI, ...args], { stdio: ['pipe', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', chunk => { stdout += String(chunk) })
    child.stderr.on('data', chunk => { stderr += String(chunk) })
    child.on('error', reject)
    child.on('close', code => resolve({ code, stdout, stderr }))
    child.stdin.end(input)
  })
}

function project() {
  return {
    title: 'SVG CLI test',
    objective: 'Verify portable SVG submission',
    audience: 'engineers',
    language: 'en',
    sections: [{ id: 'intro', title: 'Introduction', objective: 'Explain the CLI', target_words: 8 }],
    visual_contract: {
      figures: [{
        id: 'cli-flow-figure',
        section_id: 'intro',
        kind: 'diagram',
        purpose: 'Show the portable CLI flow.',
        required_labels: ['Flow'],
      }],
    },
  }
}

async function fixture(t) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-svg-cli-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, project())
  return workspace
}

test('check consumes stdin and returns a deterministic JSON verdict', async () => {
  const result = await runCli(['check'], VALID_SVG)
  assert.equal(result.code, 0)
  assert.equal(result.stderr, '')
  const verdict = JSON.parse(result.stdout)
  assert.equal(verdict.status, 'accepted')
  assert.equal(verdict.accepted, true)
})

test('check uses exit code 2 for a rejected source', async () => {
  const result = await runCli(
    ['check'],
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
  )
  assert.equal(result.code, 2)
  const verdict = JSON.parse(result.stdout)
  assert.equal(verdict.status, 'rejected')
  assert.ok(verdict.errors.includes('unsafe_tag:script'))
})

test('plan updates only the visual contract through the portable domain CLI', async t => {
  const workspace = await fixture(t)
  const contract = path.join(workspace, 'visual-contract.json')
  await writeFile(contract, JSON.stringify({
    figures: [{
      id: 'cli-flow-figure',
      section_id: 'intro',
      kind: 'diagram',
      purpose: 'Show the portable CLI flow.',
      required_labels: ['Flow'],
    }],
  }), 'utf8')
  const result = await runCli(['plan', '--workspace', workspace, '--contract', contract])
  assert.equal(result.code, 0, result.stderr)
  assert.equal(JSON.parse(result.stdout).status, 'planned')
  assert.equal((await readProject(workspace)).visual_contract.figures[0].id, 'cli-flow-figure')
})

test('submit supports an exact dry run and then controlled registration', async t => {
  const workspace = await fixture(t)
  const candidate = path.join(workspace, 'candidate.svg')
  await writeFile(candidate, VALID_SVG, 'utf8')
  const base = [
    'submit',
    '--workspace', workspace,
    '--file', candidate,
    '--id', 'cli-flow',
    '--visual-plan-id', 'cli-flow-figure',
    '--used-in', 'intro',
    '--caption', 'CLI flow diagram',
    '--alt-text', 'A concise SVG flow diagram.',
  ]

  const checked = await runCli([...base, '--dry-run'])
  assert.equal(checked.code, 0)
  assert.equal(JSON.parse(checked.stdout).status, 'checked')
  assert.equal((await readAssetManifest(workspace)).assets.length, 0)

  const registered = await runCli(base)
  assert.equal(registered.code, 0)
  const output = JSON.parse(registered.stdout)
  assert.equal(output.status, 'registered')
  assert.equal(output.asset_path, 'assets/svg/cli-flow.svg')
  assert.equal((await readAssetManifest(workspace)).assets.length, 1)
})
