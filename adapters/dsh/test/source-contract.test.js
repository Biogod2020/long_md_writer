import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../index.js', import.meta.url), 'utf8')

test('DSH lifecycle remains outside the publication kernel', () => {
  assert.match(source, /PublicationKernel/)
  assert.match(source, /runFreshReviewer/)
  assert.doesNotMatch(source, /from ['"]@longwriter\/core\/.*dsh/i)
})
