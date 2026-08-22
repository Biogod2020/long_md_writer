import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)))

async function javascriptFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const target = path.join(directory, entry.name)
    if (entry.isDirectory()) files.push(...await javascriptFiles(target))
    else if (entry.name.endsWith('.js')) files.push(target)
  }
  return files
}

test('core has no harness or protocol dependency', async () => {
  const packageJson = JSON.parse(await readFile(path.join(root, 'packages/core/package.json'), 'utf8'))
  const dependencies = Object.keys(packageJson.dependencies ?? {})
  assert.equal(dependencies.some(name => name.startsWith('@deepseek-ai/')), false)
  assert.equal(dependencies.some(name => name.startsWith('@modelcontextprotocol/')), false)

  for (const file of await javascriptFiles(path.join(root, 'packages/core/src'))) {
    const source = await readFile(file, 'utf8')
    assert.doesNotMatch(source, /from\s+['"]@deepseek-ai\//)
    assert.doesNotMatch(source, /from\s+['"]@modelcontextprotocol\//)
  }
})

test('all external entrypoints depend inward on the same core', async () => {
  for (const relative of [
    'packages/cli/src/cli.js',
    'packages/mcp/src/server.js',
    'adapters/dsh/index.js',
  ]) {
    const source = await readFile(path.join(root, relative), 'utf8')
    assert.match(source, /@longwriter\/core/)
  }
})
