# Repository operating contract

## Architecture

- `dsh-native/` is the only implementation: a DeepSeek Harness (DSH) plugin.
  DSH owns sessions, history, compaction, recovery, goals, and subagents.
- Bundle owns only publication-domain policy and three canonical workspace
  records: `project.json`, `article.md`, `assets/manifest.json`.
- Models do not decide acceptance. `python/validate_publication.py` is the
  deterministic acceptance authority; `finalize_publication` is the sole
  Goal-completion path.
- Keep version-sensitive DSH APIs in `lib/dsh-compat.js`; new session, goal,
  subagent, model, or attachment seams belong there. Keep domain logic testable.
- The SVG module splits deterministic policy in `svg/core.js`, CoreText metrics
  and geometry preflight in `svg/metrics.js` / `svg/preflight.js`, retained
  preview/review workflow in `svg/workflow.js`, controlled registration in
  `svg/submit.js`, and its narrow tool entrypoint in `svg/index.js`.
- The Mermaid module follows the same boundary: `mermaid/core.js` bounds safe
  source, `mermaid/renderer.js` runs the pinned local renderer,
  `mermaid/submit.js` retains the `.mmd` source and registers its hash-bound
  SVG derivative, and `mermaid/index.js` exposes only `mermaid_submit`.
- Canonical manuscript mutations happen only through domain tools
  (`commit_chunk`, `revise_chunk`), never through generic file writes.
- Asset additions and visual receipts are append-only through `registerAsset`
  plus approved tools (`mermaid_submit`, `svg_submit`, `svg_preflight`,
  `svg_record_review`);
  never hand-write the manifest, replace an asset, or reference one out of plan.

## Change rules

1. Never reintroduce LangGraph, the OpenAI Agents SDK/Codex control plane, or
   model-generated search/replace patch protocols.
2. Never allow generic `write`/`edit`/shell/workflow/subagent/goal tools to
   mutate or complete a publication in this profile; keep the tool guard.
3. Keep domain writes bounded: safe identifiers, balanced markers, duplicate
   rejection, control-marker injection rejection, per-workspace serialization,
   atomic replacement.
4. Do not weaken deterministic validation, asset provenance checks, hash
   binding, visual-plan/revision-chain binding, CoreText geometry evidence,
   path containment, or the review-gated completion contract.
5. Preserve the DSH version pin (`0.1.1-rc.2`) and the compatibility seam;
   read `dsh-native/DSH_COMPATIBILITY.md` before any upgrade. Upstream changes
   must be absorbed through `lib/dsh-compat.js`; do not add new direct use of
   version-sensitive DSH APIs elsewhere.
6. Add deterministic tests for every store, validator, gate, or visual change;
   they must not need credentials or a DSH service. Update
   `test/plugin-contract.test.js` for tool changes. Before submitting, run from
   `dsh-native/`: `pnpm run check:imports`, `pnpm run test:dsh-contract`, and `pnpm test`.
7. `inputs/` and `conductor/` are read-only source and historical records.
   `assets/` is append-only through the domain store: preserve existing files,
   manifests, provenance, and hashes.
8. When a tool or runtime capability changes, update README and
   architecture document in the same change so retired workflows are not
   described as current.
9. Leave manuscript context management native to DSH. Immediately before
   every `commit_chunk` or `revise_chunk`, read the complete current
   `article.md` from beginning to end in that turn; enforce this as agent
   policy, not with a second memory, summary, or context-tracking component.

## Comparison baseline

Repository comparisons use the pre-Codex (LangGraph) implementation in Git
history as the baseline ("DSH vs codex-before"). Do not treat the removed
Codex-era tree as a live reference.
