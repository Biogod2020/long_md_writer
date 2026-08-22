import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createReviewReceipt,
  createReviewRequest,
  reviewReceiptPasses,
} from '../src/review-contract.js'

const sha = 'a'.repeat(64)
const project = {
  objective: 'Test review isolation',
  quality_contract: { minimum_review_score: 85 },
}

function review() {
  return {
    article_sha256: sha,
    verdict: 'pass',
    overall_score: 92,
    summary: 'Passes.',
    critical_issues: [],
    section_findings: [{ section_id: 'intro', score: 92, findings: [] }],
    visual_findings: [],
    recommended_next_action: 'finalize',
  }
}

function execution() {
  return {
    provider: 'test-provider',
    run_id: 'run-1',
    model: 'test-model',
    isolation: 'fresh_context',
    parent_transcript_shared: false,
    read_only: true,
    output_schema_enforced: true,
    tool_allowlist: ['read'],
  }
}

test('builds a SHA-bound review receipt with runtime attestation', () => {
  const request = createReviewRequest({
    status: { article_sha256: sha, revision: 4 },
    project,
    validator: { passed: true },
  })
  const receipt = createReviewReceipt({
    request,
    review: review(),
    execution: execution(),
    currentArticleSha: sha,
    attestation: { trusted: true, attestor: 'test-runtime' },
  })
  assert.equal(receipt.article_sha256, sha)
  assert.equal(reviewReceiptPasses(receipt, project, sha), true)
})

test('rejects a reviewer that inherited the author transcript', () => {
  const request = createReviewRequest({
    status: { article_sha256: sha, revision: 4 },
    project,
    validator: { passed: true },
  })
  assert.throws(() => createReviewReceipt({
    request,
    review: review(),
    execution: { ...execution(), parent_transcript_shared: true },
    currentArticleSha: sha,
  }), /must not share/)
})

test('rejects a request without a valid shared revision', () => {
  const request = createReviewRequest({
    status: { article_sha256: sha, revision: 4 },
    project,
    validator: { passed: true },
  })
  assert.throws(() => createReviewReceipt({
    request: { ...request, expected_revision: -1 },
    review: review(),
    execution: execution(),
    currentArticleSha: sha,
  }), /expected_revision/)
})

test('an externally supplied review is retained but cannot pass finalization', () => {
  const request = createReviewRequest({
    status: { article_sha256: sha, revision: 4 },
    project,
    validator: { passed: true },
  })
  const receipt = createReviewReceipt({
    request,
    review: review(),
    execution: execution(),
    currentArticleSha: sha,
  })
  assert.equal(receipt.attestation.trusted, false)
  assert.equal(reviewReceiptPasses(receipt, project, sha), false)
})
