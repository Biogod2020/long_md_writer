import { randomUUID } from 'node:crypto'
import path from 'node:path'

import {
  appendVisualPreflight,
  appendVisualReview,
  commitChunk,
  initializeProject,
  publicationStatus,
  readAssetManifest,
  readProject,
  readRegisteredAsset,
  registerAsset,
  resolveVisualPlan,
  reviseChunk,
  setVisualContract,
  sha256Text,
} from './project-store.js'
import { runValidator } from './validator-runner.js'
import {
  acquireWorkspaceLock,
  initializeRuntimeStateLocked,
  readReviewReceipt,
  withPublicationTransaction,
  writeReviewReceipt,
} from './transaction-store.js'
import {
  createReviewReceipt,
  createReviewRequest,
  reviewReceiptPasses,
} from './review-contract.js'
import {
  checkSvg,
  preflightAsset,
  recordAssetReview,
  renderSvgToPng,
  resolvePolicy,
  submitSvg as submitSvgAsset,
} from './svg/index.js'

function expectedRevision(options = {}) {
  return options.expectedRevision ?? options.expected_revision
}

function statusWithRuntime(status, runtime) {
  return {
    ...status,
    revision: runtime.revision,
    finalized: runtime.finalized,
    finalized_at: runtime.finalized_at,
  }
}

function transactionResult(transaction) {
  if (
    transaction.result
    && typeof transaction.result === 'object'
    && !Array.isArray(transaction.result)
  ) {
    return {
      ...transaction.result,
      revision: transaction.runtime.revision,
      finalized: transaction.runtime.finalized,
      committed: transaction.committed,
    }
  }
  return {
    result: transaction.result,
    revision: transaction.runtime.revision,
    finalized: transaction.runtime.finalized,
    committed: transaction.committed,
  }
}

export class PublicationKernel {
  constructor(workspace, options = {}) {
    if (typeof workspace !== 'string' || workspace.trim().length === 0) {
      throw new TypeError('workspace must be a non-empty path')
    }
    this.workspace = path.resolve(workspace)
    this.signal = options.signal
    this.lock = options.lock
    this.svgPolicy = resolvePolicy(options.svgPolicy ?? {})
  }

  async initialize(project, options = {}) {
    const release = await acquireWorkspaceLock(this.workspace, this.lock)
    let initialized
    let runtime = null
    try {
      initialized = await initializeProject(this.workspace, project, {
        overwrite: options.overwrite === true,
      })
      if (initialized.created || options.overwrite === true) {
        runtime = await initializeRuntimeStateLocked(this.workspace, {
          operation: initialized.created ? 'initialize_publication' : 'overwrite_publication',
        })
      }
    } finally {
      await release()
    }
    if (runtime === null) {
      const transaction = await withPublicationTransaction(
        this.workspace,
        { operation: 'initialize_status', allowFinalized: true, lock: this.lock },
        async ({ state }) => ({ commit: false, result: state }),
      )
      runtime = transaction.result
    }
    return {
      created: initialized.created,
      project: initialized.project,
      status: statusWithRuntime(initialized.status, runtime),
    }
  }

  async status() {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'publication_status',
        allowFinalized: true,
        lock: this.lock,
      },
      async ({ state }) => ({
        commit: false,
        result: statusWithRuntime(await publicationStatus(this.workspace), state),
      }),
    )
    return transaction.result
  }

  async commitChunk(input, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'commit_chunk',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: {
          section_id: input?.section_id,
          chunk_id: input?.chunk_id,
          markdown_sha256: typeof input?.markdown === 'string' ? sha256Text(input.markdown) : null,
        },
      },
      async () => ({ result: await commitChunk(this.workspace, input) }),
    )
    return transactionResult({
      ...transaction,
      result: {
        committed_chunk: true,
        chunk_id: input.chunk_id,
        status: statusWithRuntime(transaction.result, transaction.runtime),
      },
    })
  }

  async reviseChunk(input, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'revise_chunk',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: {
          chunk_id: input?.chunk_id,
          markdown_sha256: typeof input?.markdown === 'string' ? sha256Text(input.markdown) : null,
        },
      },
      async () => ({ result: await reviseChunk(this.workspace, input) }),
    )
    return transactionResult({
      ...transaction,
      result: {
        revised_chunk: true,
        chunk_id: input.chunk_id,
        status: statusWithRuntime(transaction.result, transaction.runtime),
      },
    })
  }

  async planVisuals(visualContract, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'plan_visuals',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
      },
      async () => ({
        result: {
          planned: true,
          visual_contract: await setVisualContract(this.workspace, visualContract),
        },
      }),
    )
    return transactionResult(transaction)
  }

  async validate() {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'validate_publication',
        allowFinalized: true,
        lock: this.lock,
      },
      async ({ state }) => ({
        commit: false,
        result: {
          validator: await runValidator(this.workspace, this.signal),
          revision: state.revision,
        },
      }),
    )
    return transaction.result
  }

  async createReviewRequest(options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'create_review_request',
        allowFinalized: true,
        lock: this.lock,
      },
      async ({ state }) => {
        const [domainStatus, project, validator] = await Promise.all([
          publicationStatus(this.workspace),
          readProject(this.workspace),
          runValidator(this.workspace, this.signal),
        ])
        const status = statusWithRuntime(domainStatus, state)
        return {
          commit: false,
          result: createReviewRequest({
            status,
            project,
            validator,
            focus: options.focus ?? '',
          }),
        }
      },
    )
    return transaction.result
  }

  async #recordReview(input, options, attestation) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'record_publication_review',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: {
          request_id: input?.request?.request_id ?? null,
          attestor: attestation.attestor,
          trusted: attestation.trusted,
        },
      },
      async ({ state }) => {
        if (input?.request?.expected_revision !== state.revision) {
          const error = new Error(
            `review request revision conflict: expected ${input?.request?.expected_revision}, current ${state.revision}`,
          )
          error.code = 'LONGWRITER_REVISION_CONFLICT'
          throw error
        }
        const status = await publicationStatus(this.workspace)
        const receipt = createReviewReceipt({
          request: input.request,
          review: input.review,
          execution: input.execution,
          currentArticleSha: status.article_sha256,
          attestation,
        })
        const receiptFile = await writeReviewReceipt(this.workspace, receipt)
        const metadata = {
          id: receipt.id,
          path: receiptFile.path,
          sha256: receiptFile.sha256,
          article_sha256: receipt.article_sha256,
          verdict: receipt.review.verdict,
          overall_score: receipt.review.overall_score,
          provider: receipt.execution.provider,
          trusted: receipt.attestation.trusted,
          attestor: receipt.attestation.attestor,
          recorded_at: receipt.recorded_at,
        }
        return {
          result: {
            recorded: true,
            eligible_for_finalization: receipt.attestation.trusted,
            receipt,
            receipt_path: receiptFile.path,
            receipt_sha256: receiptFile.sha256,
          },
          runtimePatch: {
            review_receipts: [...state.review_receipts, metadata].slice(-200),
          },
        }
      },
    )
    return transactionResult(transaction)
  }

  async recordReview(input, options = {}) {
    return this.#recordReview(input, options, {
      trusted: false,
      attestor: 'external-unverified',
      attested_at: new Date().toISOString(),
    })
  }

  async recordAttestedReview(input, attestor, options = {}) {
    if (!attestor || typeof attestor !== 'object' || Array.isArray(attestor)) {
      throw new TypeError('trusted review attestor must be an object')
    }
    if (typeof attestor.id !== 'string' || attestor.id.trim().length === 0) {
      throw new TypeError('trusted review attestor id must be a non-empty string')
    }
    return this.#recordReview(input, options, {
      trusted: true,
      attestor: attestor.id.trim(),
      attested_at: new Date().toISOString(),
    })
  }

  async finalize(options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'finalize_publication',
        expectedRevision: expectedRevision(options),
        allowFinalized: true,
        lock: this.lock,
      },
      async ({ state }) => {
        if (state.finalized) {
          return {
            commit: false,
            result: {
              finalized: true,
              already_finalized: true,
              finalized_at: state.finalized_at,
            },
          }
        }
        const [validator, project, status] = await Promise.all([
          runValidator(this.workspace, this.signal),
          readProject(this.workspace),
          publicationStatus(this.workspace),
        ])
        if (!validator.passed) {
          return {
            commit: false,
            result: {
              finalized: false,
              reason: 'deterministic_validation_failed',
              validator,
            },
          }
        }

        let acceptedReview = null
        if (project.quality_contract.require_review !== false) {
          for (const metadata of [...state.review_receipts].reverse()) {
            if (metadata.article_sha256 !== status.article_sha256) continue
            const receipt = await readReviewReceipt(this.workspace, metadata.path, metadata.sha256)
            if (reviewReceiptPasses(receipt, project, status.article_sha256)) {
              acceptedReview = receipt
              break
            }
          }
          if (!acceptedReview) {
            return {
              commit: false,
              result: {
                finalized: false,
                reason: 'independent_review_missing_or_failed',
                article_sha256: status.article_sha256,
                minimum_review_score: project.quality_contract.minimum_review_score,
                validator,
              },
            }
          }
        }

        const finalizedAt = new Date().toISOString()
        return {
          result: {
            finalized: true,
            article_sha256: status.article_sha256,
            validator,
            review: acceptedReview,
            finalized_at: finalizedAt,
          },
          runtimePatch: {
            finalized: true,
            finalized_at: finalizedAt,
          },
        }
      },
    )
    return transactionResult(transaction)
  }

  checkSvg(source, options = {}) {
    return checkSvg(source, resolvePolicy({ ...this.svgPolicy, ...options }))
  }

  async renderSvg(source) {
    const gate = checkSvg(source, this.svgPolicy)
    if (!gate.valid) return { status: 'rejected', gate }
    const rendered = await renderSvgToPng(source)
    if (!rendered) return { status: 'error', reason: 'no_svg_renderer_available', gate }
    return { status: 'rendered', gate, ...rendered }
  }

  async submitSvg(input, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'submit_svg',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: {
          id: input?.id ?? null,
          visual_plan_id: input?.visual_plan_id ?? null,
        },
      },
      async () => {
        const result = await submitSvgAsset(this.workspace, input, {
          registerAsset,
          resolveVisualPlan,
          policy: this.svgPolicy,
        })
        return {
          result,
          commit: result?.status === 'registered',
        }
      },
    )
    return transactionResult(transaction)
  }

  async preflightSvg(input, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'preflight_svg',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: { asset_id: input?.asset_id ?? null },
      },
      async () => ({
        result: await preflightAsset(this.workspace, input, {
          registerAsset,
          readRegisteredAsset,
          readAssetManifest,
          resolveVisualPlan,
          appendVisualPreflight,
          policy: this.svgPolicy,
        }),
      }),
    )
    return transactionResult(transaction)
  }

  async recordVisualReview(input, options = {}) {
    const transaction = await withPublicationTransaction(
      this.workspace,
      {
        operation: 'record_visual_review',
        expectedRevision: expectedRevision(options),
        lock: this.lock,
        metadata: {
          asset_id: input?.asset_id ?? null,
          preflight_id: input?.preflight_id ?? null,
        },
      },
      async () => ({
        result: await recordAssetReview(this.workspace, input, { appendVisualReview }),
      }),
    )
    return transactionResult(transaction)
  }

  createExecutionEvidence(provider, overrides = {}) {
    return {
      provider,
      run_id: overrides.run_id ?? `${provider}-${randomUUID()}`,
      model: overrides.model ?? null,
      isolation: overrides.isolation ?? 'fresh_context',
      parent_transcript_shared: false,
      read_only: true,
      output_schema_enforced: true,
      tool_allowlist: overrides.tool_allowlist ?? [],
      started_at: overrides.started_at ?? null,
      completed_at: overrides.completed_at ?? new Date().toISOString(),
    }
  }
}

export function createPublicationKernel(workspace, options) {
  return new PublicationKernel(workspace, options)
}
