import assert from 'node:assert/strict'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { loadLocalEnv } from '../lib/local-env.js'

test('local env loads a missing value without overriding an existing process value', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'longwriter-env-test-'))
  const file = path.join(directory, '.env')
  const name = 'LONGWRITER_LOCAL_ENV_TEST'
  try {
    await writeFile(file, `${name}=from-file\n`)
    delete process.env[name]
    assert.equal(loadLocalEnv(file), true)
    assert.equal(process.env[name], 'from-file')

    process.env[name] = 'from-process'
    assert.equal(loadLocalEnv(file), true)
    assert.equal(process.env[name], 'from-process')
    assert.equal(loadLocalEnv(path.join(directory, 'missing.env')), false)
  } finally {
    delete process.env[name]
    await rm(directory, { recursive: true, force: true })
  }
})
