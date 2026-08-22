import assert from 'node:assert/strict'
import { appendFile, mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import os, { hostname } from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  acquireWorkspaceLock,
  readReviewReceipt,
  readRuntimeState,
  withPublicationTransaction,
  writeReviewReceipt,
} from '../src/transaction-store.js'

async function workspace(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'longwriter-runtime-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await mkdir(path.join(root, 'assets'), { recursive: true })
  await writeFile(path.join(root, 'project.json'), '{"title":"Test"}\n')
  await writeFile(path.join(root, 'article.md'), '# Test\n')
  await writeFile(path.join(root, 'assets/manifest.json'), '{"assets":[]}\n')
  return root
}

test('adopts a legacy workspace and advances one shared revision per mutation', async t => {
  const root = await workspace(t)
  const initial = await readRuntimeState(root)
  assert.equal(initial.revision, 0)

  const first = await withPublicationTransaction(root, {
    operation: 'test_append',
    expectedRevision: 0,
  }, async () => {
    await appendFile(path.join(root, 'article.md'), 'First\n')
    return { result: { ok: true } }
  })
  assert.equal(first.runtime.revision, 1)
  assert.equal(first.result.ok, true)

  await assert.rejects(
    withPublicationTransaction(root, {
      operation: 'stale_append',
      expectedRevision: 0,
    }, async () => ({ result: null })),
    error => error?.code === 'LONGWRITER_REVISION_CONFLICT',
  )
})

test('detects direct edits outside the publication kernel', async t => {
  const root = await workspace(t)
  await readRuntimeState(root)
  await appendFile(path.join(root, 'article.md'), 'out-of-band\n')
  await assert.rejects(readRuntimeState(root), /changed outside LongWriter/)
})

test('a rejected transaction does not advance revision', async t => {
  const root = await workspace(t)
  await readRuntimeState(root)
  const result = await withPublicationTransaction(root, {
    operation: 'dry_run',
  }, async () => ({ commit: false, result: { accepted: false } }))
  assert.equal(result.committed, false)
  assert.equal(result.runtime.revision, 0)
})

test('a releaser cannot remove a lock that has been replaced by another owner', async t => {
  const root = await workspace(t)
  const release = await acquireWorkspaceLock(root)
  const lock = path.join(root, '.longwriter', 'lock')
  const ownerPath = path.join(lock, 'owner.json')
  const owner = JSON.parse(await readFile(ownerPath, 'utf8'))
  await writeFile(ownerPath, JSON.stringify({ ...owner, token: 'replacement-owner' }))
  await release()
  assert.equal((await stat(lock)).isDirectory(), true)
})

test('a dead same-host owner is recovered without waiting for age expiry', async t => {
  const root = await workspace(t)
  const lock = path.join(root, '.longwriter', 'lock')
  await mkdir(lock, { recursive: true })
  await writeFile(path.join(lock, 'owner.json'), JSON.stringify({
    pid: 2147483647,
    hostname: hostname(),
    token: 'dead-owner',
  }))
  const release = await acquireWorkspaceLock(root, { timeoutMs: 1000, staleMs: 60_000 })
  await release()
})

test('review receipts are hash-bound before finalization can read them', async t => {
  const root = await workspace(t)
  const stored = await writeReviewReceipt(root, { id: 'review-1', verdict: 'pass' })
  await writeFile(path.join(root, stored.path), '{"id":"review-1","verdict":"fail"}\n')
  await assert.rejects(
    readReviewReceipt(root, stored.path, stored.sha256),
    /hash mismatch/,
  )
})
