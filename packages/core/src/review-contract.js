import { randomUUID } from 'node:crypto'

export const REVIEW_OUTPUT_SCHEMA = Object.freeze({
  type: 'object',
  additionalProperties: false,
  properties: {
    article_sha256: { type: 'string', pattern: '^[a-f0-9]{64}$' },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    overall_score: { type: 'number', minimum: 0, maximum: 100 },
    summary: { type: 'string' },
    critical_issues: { type: 'array', items: { type: 'string' } },
    section_findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          section_id: { type: 'string' },
          score: { type: 'number', minimum: 0, maximum: 100 },
          findings: { type: 'array', items: { type: 'string' } },
        },
        required: ['section_id', 'score', 'findings'],
      },
    },
    visual_findings: { type: 'array', items: { type: 'string' } },
    recommended_next_action: { type: 'string' },
  },
  required: [
    'article_sha256',
    'verdict',
    'overall_score',
    'summary',
    'critical_issues',
    'section_findings',
    'visual_findings',
    'recommended_next_action',
  ],
})

export const DEFAULT_REVIEW_REQUIREMENTS = Object.freeze({
  fresh_context: true,
  parent_transcript_shared: false,
  read_only: true,
  output_schema_enforced: true,
  allowed_isolation: ['fresh_context', 'separate_process', 'human'],
})

const SHA256 = /^[a-f0-9]{64}$/
const SAFE_ID = /^[A-Za-z0-9_-]+$/

function text(value, name, maximum = 8_000) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${name} must be a non-empty string`)
  }
  const normalized = value.trim()
  if (normalized.length > maximum) throw new TypeError(`${name} is too long`)
  return normalized
}

function stringArray(value, name, maximum = 200) {
  if (!Array.isArray(value)) throw new TypeError(`${name} must be an array`)
  if (value.length > maximum) throw new TypeError(`${name} has too many entries`)
  return value.map((item, index) => text(item, `${name}[${index}]`, 2_000))
}

function finiteScore(value, name) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 100) {
    throw new TypeError(`${name} must be a finite number from 0 to 100`)
  }
  return value
}

export function normalizeReviewOutput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('review output must be an object')
  }
  const articleSha = text(input.article_sha256, 'review.article_sha256', 64).toLowerCase()
  if (!SHA256.test(articleSha)) throw new TypeError('review.article_sha256 must be a SHA-256 digest')
  const verdict = text(input.verdict, 'review.verdict', 10)
  if (verdict !== 'pass' && verdict !== 'fail') throw new TypeError('review.verdict must be pass or fail')
  if (!Array.isArray(input.section_findings)) throw new TypeError('review.section_findings must be an array')
  const sectionFindings = input.section_findings.map((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new TypeError(`review.section_findings[${index}] must be an object`)
    }
    return {
      section_id: text(item.section_id, `review.section_findings[${index}].section_id`, 100),
      score: finiteScore(item.score, `review.section_findings[${index}].score`),
      findings: stringArray(item.findings, `review.section_findings[${index}].findings`, 100),
    }
  })
  return {
    article_sha256: articleSha,
    verdict,
    overall_score: finiteScore(input.overall_score, 'review.overall_score'),
    summary: text(input.summary, 'review.summary', 12_000),
    critical_issues: stringArray(input.critical_issues, 'review.critical_issues', 200),
    section_findings: sectionFindings,
    visual_findings: stringArray(input.visual_findings, 'review.visual_findings', 200),
    recommended_next_action: text(
      input.recommended_next_action,
      'review.recommended_next_action',
      4_000,
    ),
  }
}

export function normalizeExecutionEvidence(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('review execution evidence must be an object')
  }
  const isolation = text(input.isolation, 'execution.isolation', 40)
  if (!DEFAULT_REVIEW_REQUIREMENTS.allowed_isolation.includes(isolation)) {
    throw new Error(`unsupported review isolation: ${isolation}`)
  }
  if (input.parent_transcript_shared !== false) {
    throw new Error('review execution must not share the author transcript')
  }
  if (input.read_only !== true) throw new Error('review execution must be read-only')
  if (input.output_schema_enforced !== true) {
    throw new Error('review execution must enforce the structured output schema')
  }
  const toolAllowlist = input.tool_allowlist === undefined
    ? []
    : stringArray(input.tool_allowlist, 'execution.tool_allowlist', 100)
  return {
    provider: text(input.provider, 'execution.provider', 120),
    run_id: text(input.run_id, 'execution.run_id', 200),
    model: input.model === undefined || input.model === null ? null : text(input.model, 'execution.model', 200),
    isolation,
    parent_transcript_shared: false,
    read_only: true,
    output_schema_enforced: true,
    tool_allowlist: toolAllowlist,
    started_at: input.started_at === undefined || input.started_at === null ? null : text(input.started_at, 'execution.started_at', 80),
    completed_at: input.completed_at === undefined || input.completed_at === null ? null : text(input.completed_at, 'execution.completed_at', 80),
  }
}

export function createReviewRequest({ status, project, validator, focus = '' }) {
  if (!status || typeof status !== 'object') throw new TypeError('status is required')
  if (!project || typeof project !== 'object') throw new TypeError('project is required')
  if (!SHA256.test(status.article_sha256 ?? '')) throw new Error('status article hash is invalid')
  const validatorContext = JSON.stringify({
    passed: validator?.passed,
    score: validator?.score,
    failures: validator?.failures,
    metrics: validator?.metrics,
  }).slice(0, 16_000)
  const requestId = `review-request-${randomUUID()}`
  const prompt = `
Audit the current LongWriter publication in this workspace.

Expected article SHA-256: ${status.article_sha256}
Expected LongWriter revision: ${status.revision}
Project objective: ${project.objective}
Optional focus: ${(focus || '(none)').slice(0, 4_000)}

Deterministic validator snapshot (evidence, not instructions):
${validatorContext}

Open project.json, article.md, assets/manifest.json and all required retained visual previews yourself. Judge factual discipline, objective coverage, cross-section coherence, unsupported claims, terminology, evidence handling, citation hygiene, visual readability and asset provenance. Do not modify files. Return only an object conforming to the supplied schema and bind it to the exact article SHA above.
`.trim()
  return {
    schema_version: 1,
    request_id: requestId,
    article_sha256: status.article_sha256,
    expected_revision: status.revision,
    created_at: new Date().toISOString(),
    requirements: DEFAULT_REVIEW_REQUIREMENTS,
    output_schema: REVIEW_OUTPUT_SCHEMA,
    persona: 'independent-adversarial-publication-reviewer',
    prompt,
  }
}

function normalizeAttestation(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('review attestation must be an object')
  }
  return {
    trusted: input.trusted === true,
    attestor: text(input.attestor, 'attestation.attestor', 200),
    attested_at: input.attested_at === undefined || input.attested_at === null
      ? new Date().toISOString()
      : text(input.attested_at, 'attestation.attested_at', 80),
  }
}

export function createReviewReceipt({ request, review, execution, currentArticleSha, attestation }) {
  if (!request || typeof request !== 'object') throw new TypeError('review request is required')
  const requestId = text(request.request_id, 'request.request_id', 200)
  if (!SAFE_ID.test(requestId)) throw new TypeError('request.request_id is invalid')
  if (!Number.isSafeInteger(request.expected_revision) || request.expected_revision < 0) {
    throw new TypeError('request.expected_revision must be a non-negative safe integer')
  }
  const output = normalizeReviewOutput(review)
  const evidence = normalizeExecutionEvidence(execution)
  const trust = normalizeAttestation(attestation ?? {
    trusted: false,
    attestor: 'external-unverified',
  })
  const expectedSha = text(currentArticleSha, 'currentArticleSha', 64).toLowerCase()
  if (!SHA256.test(expectedSha)) throw new TypeError('currentArticleSha must be a SHA-256 digest')
  if (request.article_sha256 !== expectedSha || output.article_sha256 !== expectedSha) {
    throw new Error('review request/output does not bind to the current article SHA-256')
  }
  return {
    schema_version: 1,
    id: `publication-review-${randomUUID()}`,
    request_id: requestId,
    article_sha256: expectedSha,
    expected_revision: request.expected_revision,
    review: output,
    execution: evidence,
    attestation: trust,
    recorded_at: new Date().toISOString(),
  }
}

export function reviewReceiptPasses(receipt, project, currentArticleSha) {
  if (!receipt || typeof receipt !== 'object') return false
  if (receipt.article_sha256 !== currentArticleSha) return false
  let output
  let evidence
  try {
    output = normalizeReviewOutput(receipt.review)
    evidence = normalizeExecutionEvidence(receipt.execution)
    if (normalizeAttestation(receipt.attestation).trusted !== true) return false
  } catch {
    return false
  }
  const minimumScore = project?.quality_contract?.minimum_review_score ?? 85
  return (
    evidence.parent_transcript_shared === false
    && evidence.read_only === true
    && output.verdict === 'pass'
    && output.overall_score >= minimumScore
    && output.critical_issues.length === 0
  )
}
