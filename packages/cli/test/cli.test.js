import assert from 'node:assert/strict'
import test from 'node:test'

import { main } from '../src/cli.js'

test('help is available without a workspace', async () => {
  assert.equal(await main(['--help']), 0)
})
