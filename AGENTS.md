# Repository operating contract

## Architecture

- `dsh-native/` is the only implementation: a DeepSeek Harness (DSH) plugin.
  DSH owns sessions, history, compaction, recovery, goals, and subagents.
- The bundle owns only publication-domain policy and three canonical workspace
  records: `project.json`, `article.md`, `assets/manifest.json`.
- Models do not decide acceptance. `python/validate_publication.py` is the
  deterministic acceptance authority; `finalize_publication` is the only
  Goal-completion path.
- All DSH-coupled code is concentrated in `lib/dsh-compat.js`; everything else
  depends only on the domain store (`lib/project-store.js`) and validator.
- Canonical manuscript mutations happen only through domain tools
  (`commit_chunk`, `revise_chunk`), never through generic file writes.

## Change rules

1. Never reintroduce LangGraph, the OpenAI Agents SDK/Codex control plane, or
   model-generated search/replace patch protocols.
2. Never allow generic `write`/`edit`/shell/workflow/subagent/goal tools to
   mutate or complete a publication in this profile; keep the tool guard.
3. Keep domain writes bounded: safe identifiers, balanced markers, duplicate
   rejection, control-marker injection rejection, per-workspace serialization,
   atomic replacement.
4. Do not weaken deterministic validation, asset provenance checks, hash
   binding, path containment, or the review-gated completion contract.
5. Preserve the DSH version pin (`0.1.0-rc.6`) and the compatibility seam;
   read `dsh-native/DSH_COMPATIBILITY.md` before any upgrade. Upstream changes
   must be absorbed in `lib/dsh-compat.js` only.
6. Add deterministic tests for every store, validator, or gate change
   (`node --test` and `python3 -m unittest`). Tests must not require DSH
   packages or credentials.
7. `inputs/`, `assets/`, and `conductor/` are protected: source materials,
   asset library, and read-only historical records. Do not rewrite history
   documents.

## Comparison baseline

Repository comparisons use the pre-Codex (LangGraph) implementation in Git
history as the baseline ("DSH vs codex-before"). Do not treat the removed
Codex-era tree as a live reference.