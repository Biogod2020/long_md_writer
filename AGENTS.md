# Repository operating contract

## Architecture

- `codex-app-server/` is the only runtime implementation. One Codex App
  Server owns durable threads, history, compaction, recovery, structured
  clarification, goals, and streamed events.
- LongMDWriter owns publication policy and only three canonical workspace
  records: `project.json`, `article.md`, and `assets/manifest.json`.
- Models do not decide acceptance. `python/validate_publication.py` is the
  deterministic authority; a fresh read-only reviewer thread must agree, and
  `finalize_publication` is the sole Goal-completion path.
- Keep version-sensitive JSON-RPC behavior in `app-server/json-rpc-client.js`
  and `app-server/host.js`. The verified App Server baseline is Codex CLI
  `0.151.0`; upgrade it only through an explicit compatibility test.
- The root writer runs in a read-only Codex sandbox with approval policy
  `never`. Canonical writes occur only inside dynamic domain-tool handlers;
  generic shell, file change, permission, and MCP elicitation requests are
  denied by the host.
- Fresh SVG illustrator threads are the deliberate exception to the root
  profile. They run with `workspace-write`, `on-request`, and `auto_review`,
  may read the repository and publication workspace, use the internet, and
  run normal shell commands. Their only generic writable root is the retained
  per-attempt `RUN/svg-workers/JOB/attempt-N` scratch directory. A command that
  reads broadly or writes inside that scratch directory is valid SVG-worker
  work and must not be rejected merely because the root writer is read-only.
- Each run owns an isolated `.codex-home`, `run.json`, `events.jsonl`, task,
  inputs, and canonical workspace. Do not inherit the user's global plugins,
  MCP servers, skills, or approval configuration.
- `app-server/search-tools.js` exposes the repository `dsh-bing-search`
  service as four `longwriter_*` App Server dynamic function tools. Do not expose its
  native MCP namespace to third-party Responses providers; Muse 1.2 does not
  reliably route Codex namespace tool calls.
- The SVG module splits deterministic policy in `svg/core.js`, CoreText
  metrics and geometry preflight in `svg/metrics.js` / `svg/preflight.js`,
  retained review workflow in `svg/workflow.js`, controlled registration in
  `svg/submit.js`, and a narrow domain-tool adapter in `svg/index.js`.
- Asynchronous bespoke SVG work is orchestrated only by
  `app-server/svg-job-manager.js`. Initial candidates come from fresh ephemeral
  illustrator threads; revisions must use the id-addressed, in-memory,
  transactional `svg_edit` boundary in `app-server/svg-draft-editor.js` against
  the retained champion. The root remains free to continue independent work.
- Mermaid follows the same boundary: `mermaid/core.js` bounds passive source,
  `mermaid/renderer.js` runs the pinned local renderer, `mermaid/submit.js`
  retains the `.mmd` source and registers its hash-bound SVG derivative, and
  `mermaid/index.js` exposes only `mermaid_submit`.
- Web photos follow the same boundary: `image/core.js` downloads a public
  HTTP(S) image, `image/submit.js` registers `assets/photos/*` plus a PNG
  preview, and `image/index.js` exposes only `image_submit`. Search receipts
  remain host-side traces; they are not a second tool protocol.

## Change rules

1. Do not reintroduce DSH, LangGraph, the OpenAI Agents SDK, a second control
   plane, or model-generated search/replace protocols.
2. Never allow generic write/edit/shell/workflow/subagent/goal tools to mutate
   or complete a publication. Preserve the read-only root sandbox and reject
   root-writer approval escalation. This restriction does not prohibit normal
   SVG-worker shell, internet, repository-read, or scratch-write operations
   under the bounded worker profile above.
3. Keep domain writes bounded: safe identifiers, balanced markers, duplicate
   rejection, control-marker rejection, per-workspace serialization, path
   containment, and atomic replacement.
4. Do not weaken deterministic validation, provenance, hash binding,
   visual-plan/revision-chain binding, CoreText evidence, or the
   review-gated completion contract.
5. App Server dynamic tools and structured clarification are experimental
   APIs in the pinned baseline. Generate the local protocol schema and extend
   `test/app-server-contract.test.js` before changing their payloads.
6. Provider credentials must remain environment-only. Config may contain the
   provider URL and credential variable name, never a key. Do not set a model
   token limit; Muse uses `xhigh` reasoning and the Responses transport.
7. Add deterministic tests for every store, validator, gate, tool, or visual
   change. Before submitting, run from `codex-app-server/`:
   `pnpm run check:imports`, `pnpm run test:app-server-contract`, and
   `pnpm test`.
8. `inputs/` and `conductor/` are read-only sources and historical records.
   `assets/` is append-only through the domain store; never hand-edit the
   manifest, replace an asset, or cite an unregistered path.
9. When runtime capability changes, update README and
   `docs/CODEX_APP_SERVER_ARCHITECTURE.md` in the same change.
10. Leave manuscript context management native to the Codex thread.
    Immediately before every `commit_chunk` or `revise_chunk`, read the
    complete current `article.md` from beginning to end in that turn. This is
    agent policy, not a second memory, summary, or context component.

## Acceptance baseline

The supported runtime is the single Codex App Server path. Removed DSH,
Agents-SDK, and LangGraph implementations remain historical evidence only.
Promotion requires a real provider tool-call smoke, interrupted-run resume,
zero unauthorized canonical writes, and an end-to-end publication that passes
the validator and SHA-bound independent reviewer.
