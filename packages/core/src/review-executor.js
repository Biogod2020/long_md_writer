function requireExecutor(executor) {
  if (!executor || typeof executor !== 'object' || Array.isArray(executor)) {
    throw new TypeError('review executor must be an object')
  }
  if (typeof executor.id !== 'string' || executor.id.trim().length === 0) {
    throw new TypeError('review executor id must be a non-empty string')
  }
  if (typeof executor.execute !== 'function') {
    throw new TypeError('review executor must implement execute(request)')
  }
  return executor
}

/**
 * Harness-agnostic execution port. The executor controls a real isolated run;
 * Core creates the request and atomically records the result as trusted only
 * after the executor returns structured output plus runtime-owned evidence.
 */
export async function executeAndRecordReview(kernel, executor, options = {}) {
  if (!kernel || typeof kernel.createReviewRequest !== 'function'
      || typeof kernel.recordAttestedReview !== 'function') {
    throw new TypeError('kernel must implement the LongWriter review contract')
  }
  const runtime = requireExecutor(executor)
  const request = await kernel.createReviewRequest({ focus: options.focus ?? '' })
  const outcome = await runtime.execute(request)
  if (!outcome || typeof outcome !== 'object' || Array.isArray(outcome)) {
    throw new Error('review executor returned no structured outcome')
  }
  const recorded = await kernel.recordAttestedReview(
    {
      request,
      review: outcome.review,
      execution: outcome.execution,
    },
    { id: runtime.id.trim() },
    { expectedRevision: request.expected_revision },
  )
  return {
    request,
    review: outcome.review,
    execution: outcome.execution,
    recorded,
  }
}
