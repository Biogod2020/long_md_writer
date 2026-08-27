import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import test from 'node:test'

import { renderMermaidToSvg } from '../mermaid/renderer.js'

test('renderer uses the pinned CLI contract and returns its SVG', async () => {
  let invocation
  const result = await renderMermaidToSvg('flowchart LR\nA-->B', {
    cliPath: process.execPath,
    chromePath: process.execPath,
    async runProcess(command, args) {
      invocation = { command, args }
      const puppeteerConfig = args[args.indexOf('--puppeteerConfigFile') + 1]
      assert.deepEqual(JSON.parse(await readFile(puppeteerConfig, 'utf8')), {
        headless: true,
        executablePath: process.execPath,
      })
      const output = args[args.indexOf('--output') + 1]
      await writeFile(output, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0L10 10"/></svg>')
    },
  })
  assert.equal(invocation.command, process.execPath)
  assert.equal(invocation.args[0], process.execPath)
  assert.ok(invocation.args.includes('--configFile'))
  assert.ok(invocation.args.includes('--puppeteerConfigFile'))
  assert.match(result.svg, /<svg/)
  assert.equal(result.backend, 'mermaid-cli@11.16.0')
})

test('renderer rejects empty input before starting a process', async () => {
  await assert.rejects(renderMermaidToSvg(''), /non-empty string/)
})

test('renderer rejects an inaccessible explicit Chrome path', async () => {
  await assert.rejects(
    renderMermaidToSvg('flowchart LR\nA-->B', {
      cliPath: process.execPath,
      chromePath: '/definitely/not/a/chrome/binary',
    }),
    /Chrome executable is not accessible/,
  )
})
