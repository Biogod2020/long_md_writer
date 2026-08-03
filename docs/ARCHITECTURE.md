# Architecture

## Control plane versus execution plane

The system separates deterministic orchestration from agentic execution.

### Control plane

Python owns:

- job locking and atomic state persistence;
- input materialization and immutability;
- stage ordering, retries, resume, and invalidation;
- human approval gates;
- task workspace preparation;
- filesystem mutation auditing;
- artifact promotion;
- deterministic stage validation;
- Playwright rendering evidence;
- baseline no-regression comparison.

### Execution plane

An OpenAI Agents SDK manager must call a single scoped `codex_tool`. Codex receives
an isolated workspace, a precise task prompt, explicit filesystem boundaries, a
network policy, and a structured result schema. The manager cannot bypass Codex and
Codex cannot write to the canonical job directory.

## Stages

### Plan

Creates `project_brief.md` and `plan.json`. The plan is typed, versioned, and requires
unique filesystem-safe section IDs, target lengths, evidence requirements, visual
opportunities, and a quality contract.

### Draft

Each section is generated concurrently in its own private workspace. Successful
sections are collected and promoted together into immutable `drafts/`.

### Assets

Consumes immutable drafts and produces asset-resolved `md/` plus a versioned asset
manifest. Every physical visual must be registered, local, hash-bound, attributable,
and safe to render.

### Publish

Merges sections in plan order into `final.md`; HTML mode also creates a self-contained
`final.html` without remote runtime dependencies or active embeds.

### QA

Uses three separate Codex contexts:

1. independent audit, read-only except for `qa/audit-findings.json`;
2. bounded repair, only when evidence requires it;
3. fresh independent verification, read-only except for `qa_report.json`.

Between repair and verification, Python independently renders canonical desktop and
mobile screenshots. The final verifier report is hash-bound to the current audit,
publication, HTML, and browser report.

## Recovery

Each stage stores its input and artifact digests. Immutable stages require exact
digest equality for reuse. QA may intentionally update asset-resolved and published
artifacts, so resumed jobs validate their current physical quality rather than
incorrectly restoring a pre-QA digest.
