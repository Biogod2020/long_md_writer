import assert from 'node:assert/strict'
import test from 'node:test'

import { executeAndRecordReview } from '../src/review-executor.js'

test('the execution port binds a runtime result to the request revision', async () => {
  const calls = []
  const request = { request_id: 'r1', expected_revision: 7 }
  const kernel = {
    async createReviewRequest() { return request },
    async recordAttestedReview(input, attestor, options) {
      calls.push({ input, attestor, options })
      return { recorded: true }
    },
  }
  const result = await executeAndRecordReview(kernel, {
    id: 'test-runtime',
    async execute(received) {
      assert.equal(received, request)
      return { review: { verdict: 'pass' }, execution: { run_id: 'run-1' } }
    },
  })
  assert.equal(result.recorded.recorded, true)
  assert.deepEqual(calls[0].attestor, { id: 'test-runtime' })
  assert.deepEqual(calls[0].options, { expectedRevision: 7 })
})
