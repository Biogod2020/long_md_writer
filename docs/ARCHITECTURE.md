# LongWriter architecture

LongWriter is a publication control plane, not a general agent harness.

```text
Agent Skill (workflow policy)
          |
   CLI / MCP / DSH adapter
          |
  @longwriter/core
  - canonical publication store
  - cross-process revision lock
  - deterministic validator
  - review request/receipt gate
  - SVG evidence workflow
```

## Ownership boundary

`@longwriter/core` owns every publication invariant. It has no dependency on
DSH, MCP, an LLM provider, conversation history, or a subagent API. CLI and MCP
are equivalent interfaces. The DSH package is an optional adapter for Goals,
session continuation, and fresh child-agent execution.

The human-readable truth remains `project.json`, `article.md`, and
`assets/manifest.json`. `.longwriter/state.json` adds shared revision,
finalization state, immutable review receipts, a cross-process lock, and an
operation ledger. The hidden state does not duplicate manuscript content.

## Mutation model

Every controlled mutation is serialized from the caller's perspective and
advances one shared revision. Callers may supply `expected_revision`; stale
writes fail before mutation. A snapshot hash detects direct edits outside Core.
Read-only validation and review-request creation do not advance revision.

## Independent review

Core does not expose `spawn_subagent`. It emits a review execution contract and
accepts a structured result plus runtime attestation. Generic CLI/MCP submissions
are stored as unverified evidence; only an adapter that actually controlled the
isolated execution may use Core's trusted attestor path. Finalization accepts
only a receipt bound to the current article SHA, with qualifying isolation, a
passing verdict, no critical issue, and the project's minimum score.

## Non-goals

Core does not own model loops, context compaction, web search, general tool
execution, or multi-agent team topology. Those remain host-runtime concerns.
