import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../src/server.js', import.meta.url), 'utf8')

test('MCP remains a thin stateless adapter over PublicationKernel', () => {
  assert.match(source, /new PublicationKernel\(input\.workspace\)/)
  assert.doesNotMatch(source, /subagents|conversation|session/i)
  for (const name of [
    'initialize_publication',
    'publication_status',
    'commit_chunk',
    'revise_chunk',
    'create_review_request',
    'record_publication_review',
    'finalize_publication',
  ]) {
    assert.match(source, new RegExp(`'${name}'`))
  }
})
