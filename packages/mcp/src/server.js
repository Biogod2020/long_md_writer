#!/usr/bin/env node

import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { McpServer } from '@modelcontextprotocol/server'
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio'
import * as z from 'zod/v4'

import { PublicationKernel } from '@longwriter/core'

const workspace = z.string().min(1).describe('Absolute or relative publication workspace path.')
const expectedRevision = z.number().int().nonnegative().optional().describe(
  'Optimistic concurrency revision returned by publication_status.',
)
const jsonObject = z.record(z.string(), z.unknown())

function mutationOptions(input) {
  return input.expected_revision === undefined
    ? {}
    : { expectedRevision: input.expected_revision }
}

function kernel(input) {
  return new PublicationKernel(input.workspace)
}

function result(value) {
  return {
    content: [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    structuredContent: value,
  }
}

function register(server, name, definition, handler) {
  server.registerTool(name, definition, async input => result(await handler(input)))
}

export function buildServer() {
  const server = new McpServer({
    name: 'longwriter',
    version: '0.2.0',
  })

  register(server, 'initialize_publication', {
    description: 'Create the canonical LongWriter publication files and hidden revision state.',
    inputSchema: z.object({
      workspace,
      project: jsonObject,
      overwrite: z.boolean().optional(),
    }),
  }, input => kernel(input).initialize(input.project, { overwrite: input.overwrite === true }))

  register(server, 'publication_status', {
    description: 'Read manuscript progress, article SHA-256, shared revision, and finalization state.',
    inputSchema: z.object({ workspace }),
  }, input => kernel(input).status())

  register(server, 'commit_chunk', {
    description: 'Atomically append one Markdown chunk to a planned section.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      section_id: z.string().min(1),
      chunk_id: z.string().min(1),
      markdown: z.string().min(1),
    }),
  }, input => kernel(input).commitChunk({
    section_id: input.section_id,
    chunk_id: input.chunk_id,
    markdown: input.markdown,
  }, mutationOptions(input)))

  register(server, 'revise_chunk', {
    description: 'Atomically replace the complete contents of one existing Markdown chunk.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      chunk_id: z.string().min(1),
      markdown: z.string().min(1),
    }),
  }, input => kernel(input).reviseChunk({
    chunk_id: input.chunk_id,
    markdown: input.markdown,
  }, mutationOptions(input)))

  register(server, 'plan_visuals', {
    description: 'Replace project.json.visual_contract through the publication kernel.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      visual_contract: jsonObject,
    }),
  }, input => kernel(input).planVisuals(input.visual_contract, mutationOptions(input)))

  register(server, 'validate_publication', {
    description: 'Run deterministic publication validation without changing the revision.',
    inputSchema: z.object({ workspace }),
  }, input => kernel(input).validate())

  register(server, 'create_review_request', {
    description: 'Create a SHA- and revision-bound independent-review execution contract.',
    inputSchema: z.object({
      workspace,
      focus: z.string().max(4000).optional(),
    }),
  }, input => kernel(input).createReviewRequest({ focus: input.focus ?? '' }))

  register(server, 'record_publication_review', {
    description: 'Retain an externally supplied review as unverified evidence. It cannot satisfy the finalization gate; a trusted runtime adapter must attest execution.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      request: jsonObject,
      review: jsonObject,
      execution: jsonObject,
    }),
  }, input => kernel(input).recordReview({
    request: input.request,
    review: input.review,
    execution: input.execution,
  }, mutationOptions(input)))

  register(server, 'finalize_publication', {
    description: 'Finalize only when deterministic validation and the stored independent review gate pass.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
    }),
  }, input => kernel(input).finalize(mutationOptions(input)))

  register(server, 'svg_check', {
    description: 'Deterministically inspect caller-supplied SVG source without writing files.',
    inputSchema: z.object({
      svg: z.string().min(1),
      accept_score: z.number().min(0).max(100).optional(),
    }),
  }, input => new PublicationKernel(process.cwd()).checkSvg(
    input.svg,
    input.accept_score === undefined ? {} : { acceptScore: input.accept_score },
  ))

  register(server, 'svg_submit', {
    description: 'Check and register a planned SVG asset; dry runs never advance the publication revision.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      svg: z.string().min(1),
      visual_plan_id: z.string().min(1),
      id: z.string().min(1).optional(),
      supersedes_asset_id: z.string().min(1).optional(),
      caption: z.string().min(1),
      alt_text: z.string().min(1),
      source: z.string().min(1).optional(),
      provenance: z.string().min(1).optional(),
      licence: z.string().min(1).optional(),
      used_in: z.array(z.string().min(1)).default([]),
      dry_run: z.boolean().optional(),
      accept_score: z.number().min(0).max(100).optional(),
    }),
  }, input => kernel(input).submitSvg({
    svg: input.svg,
    visual_plan_id: input.visual_plan_id,
    id: input.id,
    supersedes_asset_id: input.supersedes_asset_id,
    caption: input.caption,
    alt_text: input.alt_text,
    source: input.source,
    provenance: input.provenance,
    licence: input.licence,
    used_in: input.used_in,
    dry_run: input.dry_run === true,
    accept_score: input.accept_score,
  }, mutationOptions(input)))

  register(server, 'svg_preflight', {
    description: 'Retain a PNG preview and append deterministic geometry evidence for a registered SVG.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      asset_id: z.string().min(1),
    }),
  }, input => kernel(input).preflightSvg(
    { asset_id: input.asset_id },
    mutationOptions(input),
  ))

  register(server, 'svg_record_review', {
    description: 'Append a hash-bound visual inspection receipt for a retained SVG preview.',
    inputSchema: z.object({
      workspace,
      expected_revision: expectedRevision,
      asset_id: z.string().min(1),
      preflight_id: z.string().min(1),
      reviewer: z.string().min(1),
      verdict: z.enum(['pass', 'fail']),
      summary: z.string().min(1),
      findings: z.array(z.string()).default([]),
      checked_labels: z.array(z.string()).default([]),
    }),
  }, input => kernel(input).recordVisualReview({
    asset_id: input.asset_id,
    preflight_id: input.preflight_id,
    reviewer: input.reviewer,
    verdict: input.verdict,
    summary: input.summary,
    findings: input.findings,
    checked_labels: input.checked_labels,
  }, mutationOptions(input)))

  return server
}

export async function main() {
  const server = buildServer()
  await server.connect(new StdioServerTransport())
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`)
    process.exitCode = 1
  })
}
