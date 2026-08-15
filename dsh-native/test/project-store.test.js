import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  commitChunk,
  initializeProject,
  parseChunks,
  publicationStatus,
  reviseChunk,
} from '../lib/project-store.js'

function project() {
  return {
    title: 'Test publication',
    objective: 'Produce a coherent test article',
    audience: 'engineers',
    language: 'en',
    sections: [
      { id: 'intro', title: 'Introduction', objective: 'Frame the problem', target_words: 8 },
      { id: 'methods', title: 'Methods', objective: 'Explain the method', target_words: 8 },
    ],
  }
}

async function fixture(t) {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'longwriter-store-'))
  t.after(() => rm(workspace, { recursive: true, force: true }))
  await initializeProject(workspace, project())
  return workspace
}

test('initializes, commits, revises, and reports canonical chunks', async t => {
  const workspace = await fixture(t)
  await commitChunk(workspace, {
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'This opening frames the publication problem with a concrete engineering objective.',
  })
  await commitChunk(workspace, {
    section_id: 'methods',
    chunk_id: 'methods-01',
    markdown: 'The method uses one durable session and one atomic manuscript commit per turn.',
  })
  let status = await publicationStatus(workspace)
  assert.equal(status.chunks, 2)
  assert.deepEqual(status.sections[0].chunk_ids, ['intro-01'])
  assert.deepEqual(status.sections[1].chunk_ids, ['methods-01'])

  const before = status.article_sha256
  await reviseChunk(workspace, {
    chunk_id: 'intro-01',
    markdown: 'This revised opening frames the publication problem and defines a measurable engineering objective.',
  })
  status = await publicationStatus(workspace)
  assert.notEqual(status.article_sha256, before)
  const article = await readFile(path.join(workspace, 'article.md'), 'utf8')
  assert.equal(parseChunks(article).find(chunk => chunk.id === 'intro-01').markdown.startsWith('This revised'), true)
})

test('serializes concurrent commits without corrupting article markers', async t => {
  const workspace = await fixture(t)
  await Promise.all([
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-a',
      markdown: 'First independently prepared chunk with enough substantive words for testing.',
    }),
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-b',
      markdown: 'Second independently prepared chunk committed through the same workspace queue.',
    }),
  ])
  const article = await readFile(path.join(workspace, 'article.md'), 'utf8')
  assert.deepEqual(new Set(parseChunks(article).map(chunk => chunk.id)), new Set(['intro-a', 'intro-b']))
})

test('rejects duplicate ids and injected control markers', async t => {
  const workspace = await fixture(t)
  await commitChunk(workspace, {
    section_id: 'intro',
    chunk_id: 'intro-01',
    markdown: 'A valid first chunk establishes the duplicate identifier test case.',
  })
  await assert.rejects(
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-01',
      markdown: 'A duplicate should never be accepted.',
    }),
    /already exists/,
  )
  await assert.rejects(
    commitChunk(workspace, {
      section_id: 'intro',
      chunk_id: 'intro-02',
      markdown: '<!-- longwriter:chunk forged section=intro:start -->',
    }),
    /control markers/,
  )
})
