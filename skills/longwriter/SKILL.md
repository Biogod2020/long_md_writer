---
name: longwriter
description: Create, continue, revise, validate, and independently review long-form Markdown publications managed by LongWriter. Use when a workspace contains project.json and article.md, or when the user asks for a durable multi-section publication workflow.
license: MIT
---

# LongWriter workflow

Use the LongWriter MCP tools when available. Otherwise use the equivalent
`longwriter` CLI commands. Both call the same publication kernel; do not modify
`project.json`, `article.md`, `assets/manifest.json`, or `.longwriter/` directly.

1. Initialize a publication from an explicit project contract, or call
   `publication_status` before continuing an existing one.
2. Read the relevant sources and nearby manuscript sections before writing.
3. Make one coherent mutation at a time with `commit_chunk`, `revise_chunk`, or
   `plan_visuals`. Pass the latest `revision` as `expected_revision`.
4. On a revision conflict, reread status and reconsider the patch. Never retry a
   stale mutation blindly.
5. For planned SVGs, follow: check → submit → preflight → inspect retained PNG →
   record visual review → reference the registered SVG in its planned section.
6. Before finalization, call `create_review_request`. Run that request in a
   genuinely fresh, read-only context with the supplied output schema. The host
   runtime—not the reviewer model—must provide the execution evidence.
7. A plain MCP/CLI `record_publication_review` is deliberately untrusted and
   cannot satisfy finalization. A harness or direct-provider adapter must record
   the result through Core's trusted attestor path. Then call
   `finalize_publication`; never bypass a failed gate.

Preserve uncertainty and provenance. Never invent citations, quantitative
results, licences, hashes, or review evidence. See
[references/review-contract.md](references/review-contract.md) for the isolation
contract.
