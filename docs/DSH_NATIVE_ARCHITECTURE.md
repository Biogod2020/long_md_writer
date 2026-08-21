# DSH-native LongMDWriter architecture

## Status

`dsh-native/` is the repository's only implementation. Earlier LangGraph and
Codex-era controllers remain comparison material in Git history, not live
runtime references. The current design keeps the acceptance path measurable
without recreating their controller state.

## Core judgment

The previous five-stage controller solved constraints imposed by bounded, isolated Codex tasks:

```text
plan -> draft -> assets -> publish -> qa
```

It therefore had to implement stage state, attempts, digests, staging copies, promotion, event logs, resume rules, and context separation in Python.

DSH already owns the corresponding harness concerns through its Session event log, persistence seam, Agent loop, compaction, Goal domain, Goal Round Driver, tool pipeline, and subagent service. Recreating the five stages inside DSH would preserve most of the accidental complexity.

The new design instead uses one long-lived root Agent:

```text
Root DSH Session
  -> inspect current workspace and retained history
  -> research/read/reason across multiple steps
  -> commit or revise exactly one chunk
  -> terminal tool concludes the turn
  -> Goal Round Driver starts the next round
```

## State boundaries

### DSH-owned runtime state

- full typed event log;
- model-visible derived history;
- tool calls and results;
- compaction checkpoints;
- crash recovery and resume;
- current durable Goal and round count;
- reviewer child Sessions and lifecycle.

No LongMDWriter event log, retry counter, stage checkpoint, context packet, or summary database is added.

### LongMDWriter-owned domain state

`project.json` is structural truth: objective, audience, sections, word targets,
evidence requirements, quality thresholds, and `visual_contract` figure plans.

`article.md` is the single canonical manuscript. Section and chunk comments are deterministic addressing metadata, not an LLM action protocol.

`assets/manifest.json` is provenance truth for physical assets. It also appends
hash-bound visual preflight and review receipts; it remains separate because
hashes, licences, local paths, use sites, and evidence records are publication
facts rather than conversation history.

## Turn and step semantics

“One turn writes one chunk” means one successful root turn may commit at most one manuscript chunk. It does not mean one model request per chunk.

A typical turn is:

```text
step 1: publication_status
step 2: read earlier prose
step 3: search or inspect evidence
step 4: commit_chunk
turn end: concludesTurn
```

`commit_chunk`, `revise_chunk`, `review_publication`, `initialize_publication`,
`plan_visuals`, `resume_publication`, and `finalize_publication` are terminal
tools. `publication_status` is nonterminal.

This preserves fast sequential generation while allowing each chunk to receive enough evidence and local context before mutation.

## Goal loop

`initialize_publication` creates an armed DSH Goal whose objective equals `project.json.objective`. The upstream Goal Round Driver schedules another same-session round whenever the Agent becomes idle while the Goal remains active and armed.

The generic DSH goal tool is disabled. The model cannot self-certify completion through `update_goal(action=complete)`. Only `finalize_publication` may call the Goal service's completion method after deterministic and independent checks.

After Session resume, DSH deliberately restores durable Goal state as disarmed. `resume_publication` verifies the workspace objective and explicitly re-arms continuation.

## Tool versus subagent mapping

Deterministic operations remain tools:

- project initialization;
- status calculation;
- atomic chunk insertion and replacement;
- hashing and validation;
- SVG evidence: the agent first records a section-bound visual plan, draws the
  source, then `svg_check` reports deterministic safety/structure findings and
  `svg_submit` appends `assets/svg/<id>.svg`; `svg_preflight` uses local
  CoreText geometry measurement, retains a registered PNG preview, and appends
  a hash-bound receipt; after image inspection, `svg_record_review` appends the
  independent review receipt. A failed candidate is historical and can only be
  corrected through one explicit append-only successor;
- future image-search and asset-registration APIs.

A capability becomes a subagent only when it needs its own decide-act-observe loop. The first such capability is independent review.

`review_publication` is a domain tool backed by a fresh `spawn` subagent. The root sees one stable publication API; the child owns its own Session, can make several read/tool/model steps, and returns one structured result. This avoids exposing a generic delegation surface to the writer.

## Context strategy

DSH Session history is the episodic and working memory. Automatic compaction handles long-running conversation pressure.

The manuscript is external canonical memory. The root Agent reads relevant ranges rather than permanently injecting the full article into every request. This avoids quadratic prompt growth and makes compaction loss nonfatal.

`AGENTS.md` remains compatible with the upstream agent-instructions plugin and can carry repository-level policy. The LongMDWriter bundle adds a stable system-prompt section for publication-specific loop behavior.

## Mutation security

The dedicated profile disables model-facing shell, workflow, Ralph, generic subagent, string-replace, and generic goal-completion tools.

The upstream filesystem reader remains useful. A monotonic DSH tool guard rejects every generic `write` or `edit` call in the dedicated profile. Canonical manuscript changes therefore pass through the domain store, which provides:

- safe identifiers;
- balanced section/chunk markers;
- duplicate rejection;
- control-marker injection rejection;
- per-workspace serialization;
- atomic replacement.

This is a smaller and more direct boundary than whole-workspace snapshots for every writing step.

## Completion gate

`finalize_publication` follows this sequence:

```text
deterministic validator
  -> fail: return exact checks, keep Goal active
  -> pass: fresh reviewer subagent
       -> stale hash / low score / critical issue: keep Goal active
       -> pass: complete Goal and conclude turn
```

The reviewer is bound to the current article SHA-256. A review of an earlier article cannot certify a later edit.

The validator covers project schema, marker integrity, planned section headings,
per-section and total length, placeholders, asset registration, local
references, provenance, and physical hashes. For every planned SVG it also
requires a single active revision-chain tip in its planned section, required
text labels, a CoreText-backed geometry preflight, a retained PNG derivative,
and a hash-bound passing review. Models cannot bypass this evidence chain.

## Upstream-change containment

The integration is an official out-of-tree DSH bundle. It does not fork or patch the DSH repository.

Compatibility measures:

1. exact release and upstream commit pin;
2. public package root imports only;
3. DSH calls concentrated in `lib/dsh-compat.js`;
4. mount-time capability probes;
5. versioned Session storage directories;
6. canonical workspace files as cross-version recovery truth;
7. pinned CI plus a nonblocking latest-version probe;
8. manual upgrade promotion after a live crash/compaction/reviewer/resume test.

## Migration sequence

### Milestone 1 — implemented here

- out-of-tree bundle;
- root publication policy;
- durable Goal and same-session continuation;
- three-file canonical workspace;
- atomic chunk commit/revision;
- fresh structured reviewer;
- deterministic finalize gate;
- visual plans, CoreText geometry preflight, retained PNG evidence, and
  hash-bound review receipts;
- update-isolation policy and tests.

### Milestone 2

- native image-search service/provider/tool;
- asset download, licence verification, and registration;
- citation/evidence tools;
- stronger section-range reads for very large manuscripts.

### Milestone 3

- HTML renderer tool;
- Playwright browser evidence tool;
- richer browser-based rendering review beyond retained SVG previews;
- baseline no-regression evaluator.

### Removal gate for the old runtime

The Python/Codex controller should be removed only after the DSH path demonstrates, on representative historical jobs:

- no reduction in deterministic pass rate;
- successful forced compaction;
- successful interrupted-turn recovery;
- stable Session resume across process restarts on the pinned version;
- zero unauthorized canonical-file mutations;
- reviewer and finalizer hash consistency;
- acceptable cost and time for long publications.
