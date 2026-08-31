# Codex App Server architecture

## Runtime boundary

LongMDWriter has one control plane: `codex app-server --stdio`. A durable root
thread owns conversation history, compaction, clarification, recovery, the
active Goal, and model/tool events. LongMDWriter does not maintain a second
memory or workflow database.

Each run is self-contained:

```text
runs/<run-id>/
├── task.txt
├── run.json                 resumable thread id, Goal, rounds, status
├── events.jsonl             exact App Server request/event trace
├── .codex-home/             isolated thread persistence and configuration
└── workspace/
    ├── inputs/              read-only source material
    ├── project.json         structure and quality/visual contracts
    ├── article.md           canonical manuscript
    └── assets/manifest.json provenance, image-search receipts, visual evidence
```

The isolated Codex home prevents unrelated global plugins, MCP servers,
skills, approval rules, or model configuration from entering the provider
request. This is also required for providers that reject recursive schemas
from unrelated global tools.

## Goal and turn loop

Before the first model turn, the host sets a provisional scientific Goal that
defines evidence discipline and evaluator-gated completion. The
`initialize_publication` tool replaces it with a project-specific Goal naming
the audience, language, section objectives, word targets, visual evidence,
and exact completion gate.

The CLI advances the same thread one coherent unit per turn. Terminal tools
are `initialize_publication`, `plan_visuals`, `commit_chunk`, `revise_chunk`,
`review_publication`, and `finalize_publication`. The dynamic-tool runtime
rejects a second terminal call in one turn. Before every manuscript mutation,
the agent must read all of `article.md`; Codex still owns history and
compaction, so no manuscript-memory component is added.

`run.json` persists the thread id and completed round count. `resume` rejoins
the same App Server thread and continues from canonical workspace records. At
preparation time it also records a deterministic fingerprint of the runtime
source set, including provider config, so runs remain reproducible even from a
dirty or not-yet-committed checkout.
An optional `resume --instruction-file FILE` adds one operator-reviewed next
unit to that same thread and records the file path and hash in run metadata;
it does not mutate canonical files or bypass publication tools.
If the host's dynamic-tool contract itself changes, `restart` creates a new
durable thread over the same canonical workspace and records the superseded
thread id; App Server fixes dynamic tools at thread creation.

The latest independent publication-review verdict is retained in `run.json`
as a compact article-SHA-bound scheduling receipt. A passing receipt advances
the next turn to `finalize_publication`; a failed receipt blocks unchanged
re-review and asks for a bounded manuscript revision. It does not become
publication state: `project.json`, `article.md`, and `assets/manifest.json`
remain the only canonical workspace records.

Asynchronous SVG job metadata is retained in the same `run.json` scheduling
record. It contains job status, bounded attempt counts, the current champion
asset/hash, locked passes, and compact findings; it is not a fourth canonical
workspace record. An interrupted `running` or `revising` job is restored as
`queued` and resumes from its retained champion after host restart.

`review_publication` is validator-gated: a deterministic failure returns
immediately without spawning fresh visual or manuscript reviewers. This keeps
expensive independent review behind the same eligibility boundary already used
by `finalize_publication`. Scheduler guidance separately checks the initialized
total-length ratio, chooses the chunk with the largest safe reduction capacity,
and forbids another review call in that revision turn.

## Mutation and approval security

The root and reviewer threads use `sandbox: read-only`. The root also uses
`approvalPolicy: never`; the host rejects any command, file-change, permission,
or MCP-elicitation approval callback. Therefore generic Codex tools may inspect
the workspace but cannot mutate it or escalate around the boundary.

SVG illustrator threads use a separate execution profile. Each fresh attempt
starts in `RUN/svg-workers/JOB/attempt-N` with `workspace-write`, `on-request`,
and `auto_review` (the Codex “Approve for me” mode). `turn/start` supplies an
explicit `workspaceWrite` policy whose only writable root is that scratch
directory, excludes the default `/tmp` and `$TMPDIR` write exceptions, and has
`networkAccess` enabled. The illustrator may read the
repository and canonical workspace, use the internet, and run routine shell
commands for inspection, calculation, font discovery, and local rendering.
The repository contract scopes the root writer's read-only rule away from these
worker operations so auto-review can evaluate a safe scratch write against the
worker profile instead of the root profile.
The scratch directory is retained for audit. It is not a canonical record and
cannot replace the host-owned publication stores.

Canonical mutations run in the client-owned dynamic domain tools. The store
enforces identifiers, markers, duplicate rejection, injection rejection,
serialization, path containment, hashes, and atomic writes. Provider
credentials stay in the named environment variable and never enter config,
run state, or event logs.

## Clarification and inputs

The initial turn includes the task and source paths. Images may be supplied as
native local-image inputs; other documents are copied to `workspace/inputs/`
with SHA-256 receipts. If the task already states a measurable contract
(sections, length, visuals, research), skip clarification and initialize from
it. Only then does the model use one App Server `request_user_input` item for
remaining user-owned ambiguity. The interactive CLI returns the answer to the
same turn. A non-interactive run fails explicitly if the model still requests
clarification instead of guessing.

## Search and visuals

The repository `dsh-bing-search` service is reused behind four flat dynamic
functions: `longwriter_search`, `longwriter_search_images`, `longwriter_open`,
and `longwriter_find`. `app-server/search-tools.js` invokes its pinned Python
service through `scripts/search-tool.py`. This deliberately avoids native MCP
namespace tool encoding, which iWorld Muse 1.2 cannot route reliably, while
preserving the existing search implementation and its safety checks.
An optional run-level research gate counts successful calls in `run.json` and
can prevent `plan_visuals` until web search, image search, and source opening
have actually occurred. Successful image searches are also projected into the
canonical manifest as append-only, hash-bound candidate receipts containing
source pages and relevance metadata. The validator enforces project-level
minimum search and candidate counts. Search and drawing are ordinary App Server function tools the writer calls
while working. Successful image searches still leave compact host-side receipts
in the manifest so the research contract can be checked; the writer does not
have to name those receipts. `image_submit` downloads a public image URL and
registers a hash-bound local photo under `assets/photos/`. The manuscript may
cite only registered workspace assets, never a hotlinked URL. The visual-plan
minimum is a floor, not the target. Host receipts are trace policy, not a
second manuscript memory.

Mermaid, bespoke SVG, and retained photos all require a visual plan, controlled
registration, a hash-bound preflight, and `inspect_visual` before manuscript
citation. `inspect_visual` resolves the exact current source and retained PNG,
then starts one ephemeral read-only App Server thread with exactly one
`localImage`. The host checks every returned id, source hash, preview hash,
preflight id, verdict, and required label before appending an
`independent_visual_review` receipt. The durable root receives only compact
text JSON. It never receives an App Server `inputImage` tool result, and the host
rejects any future domain result that attempts to return an inline image. The
review turn also carries a dedicated no-tool collaboration instruction. A
shell, file, web, MCP, image-view, or agent-tool event causes immediate
interruption; that turn cannot become evidence. The complete bound is three independent attempts:
the initial turn plus at most two fresh-thread retries. A fail verdict must also
carry at least one actionable finding; an empty finding list is a protocol
failure rather than review evidence.

Failed SVG preflights use the same one-image, tool-free model boundary in a
strictly diagnostic mode. The bound PNG, representative deterministic issues,
scientific criteria, and publication width are sent to a fresh ephemeral
thread. Its pixel-grounded findings are fed to the next `svg_edit` worker, but
the response is recorded only as a run event: it cannot create a manifest
review receipt, change acceptance fitness, lock a pass, authorize citation, or
bypass deterministic preflight. Acceptance-mode `inspect_visual` remains
passing-preflight-only.

Visual-contract schema v2 binds every figure to a figure type, a final single-
or double-column publication width, a falsifiable scientific claim, exact
scientific checks, and a reading order. SVG preflight uses local CoreText
metrics to enforce an 8 pt final-size floor, text-density and font-tier limits,
canvas use and balance, contrast, overlap, and connector-to-text clearance.
Issue sets above 100 entries are compacted deterministically across categories
with explicit total and omitted counts before retention. This preserves the
bounded manifest contract while giving SVG workers representative actionable
feedback instead of a list-size error.
The one-image reviewer then handles the non-deterministic boundary: scientific
completeness and conservation, semantic visual grammar, hierarchy, text
economy, composition, palette/dual encoding, reading order, and aesthetics.

Bespoke SVG creation has a separate asynchronous orchestration boundary inside
the same App Server host. The durable root calls `svg_delegate`, receives a job
id immediately, and continues an independent prose or research unit. A bounded
pool starts fresh ephemeral `longwriter-svg-worker` threads, so an illustrator
does not inherit the author's long conversation or another illustrator's
failed reasoning. Initial creation returns one complete SVG with stable DOM
ids. Every later attempt receives the retained champion and one narrow
`svg_edit` dynamic tool. The tool applies either one operation or an atomic batch
of up to 16 id-addressed DOM operations to an in-memory draft
(`set_attributes`, `set_text`, `remove`, or bounded `append_fragment`), validates
the complete transaction once, and rolls the whole batch back on unsafe or
malformed output. A revision worker cannot submit a replacement SVG source; the
host accepts only its own edited draft and checks the reported edit revision
before submission. After a plan has entered this delegated path, the root
`svg_submit` tool rejects that plan regardless of whether the job is active,
passed, or exhausted; this prevents a second, unreviewed revision chain.

The workers are not tool-free: both initial and revision turns may use shell
and internet access within the SVG execution profile. Initial delivery still
comes from the structured SVG output, while every revision to an accepted
champion still crosses only the transactional `svg_edit` boundary. Temporary
files created by shell commands remain in the attempt scratch directory.
Initial workers also receive `svg_preflight_candidate`; revision workers receive
`svg_preflight_draft`. These read-only tools run the exact publication preflight
without registering a candidate and return bounded findings with stable text and
shape ids. A per-attempt check budget prevents preflight loops. The host counts
general command executions and, after the configured delivery threshold, uses
App Server `turn/steer` to append a delivery checkpoint to the same active turn.
This is a soft convergence signal, not a permission downgrade: broad reads,
network access, shell access, and scratch writes remain available.

Preflight excludes text hidden by opacity, display, or visibility from geometry
and required-label evidence. A visible typographic construction may expose its
canonical spelling through `aria-label` only when Unicode compatibility
normalization proves it equivalent to the painted text. This supports robust
ASCII-glyph tspan superscripts/subscripts while rejecting hidden exact-label
duplicates. CoreText records the resolved font and missing characters; unstable
compatibility glyph runs fail with an id-addressed repair finding, while ordinary
font fallback remains explicit diagnostic evidence for the independent PNG
reviewer rather than an automatic rejection.
The final Python publication validator repeats the same inherited-visibility
and typographic-equivalence checks, so an asset cannot pass worker preflight and
then fail publication review merely because its exact formula is represented by
an equivalent visible tspan construction.

The SVG job manager uses a champion-challenger gate to prevent repair
oscillation. Deterministic preflight passes, confirmed labels, scientific
checks, and design checks become a monotonic locked-pass ledger. A challenger
that regresses any locked pass cannot replace the champion, even if it fixes a
different finding. Duplicate source hashes consume the bounded attempt budget
without another registration. Actionable feedback for the next worker is
stored with the champion. For failed preflights, exact deterministic
id-addressed findings are placed before a bounded pixel-diagnostic list, and minimum-font
findings explicitly prohibit shrinking text as an overlap repair. A rejected
challenger's transient geometry does
not send the next worker after defects that are absent from its baseline.
Repeated failure signatures switch from a
surgical edit strategy to a simpler grid/layout edit, still against the same
id-addressed champion rather than a redraw. The default pool allows two
concurrent jobs (with an explicit controlled maximum of six), eight attempts per job,
and a two-repeat stagnation threshold;
each revision worker also has a default 24-call local edit budget. Dedicated
preflight calls and the general-command delivery threshold are independently
bounded by host config. Continuation scheduling dispatches one undelegated SVG
per turn until the configured pool is full, then returns the root to independent
prose or research while the workers run.
Successful delegation is a host-enforced terminal turn unit: the host interrupts
the root turn after the job id is returned, so provider-side failure to obey a
textual “stop” instruction cannot delay subsequent pool scheduling.
An exhausted plan does not abort already-delegated peers: continuation prompts
wait until every active peer is terminal, then the host reports the bounded
failure with all batch evidence retained.
bounded in config. A later fresh job for the same visual inherits the
best retained champion instead of starting over, but each visual plan has a
default three-job generation ceiling. Exhausting that ceiling fails explicitly
with retained evidence instead of creating jobs forever.

Exact repeat inspections can reuse an existing receipt only when all bindings
and the reviewer model/provider/effort configuration hash match. Ephemeral
reviewer threads are unsubscribed after their single turn. This keeps native
Codex history management while preventing base64 image bytes from accumulating
in the durable root conversation.

After each terminal publication unit, the host derives the next prompt from
`project.json`, `article.md`, and `assets/manifest.json`: gated research and an
empty visual plan first; then underfilled prose; length or long-sentence
violations; missing current asset, preflight, independent check, or article
citation; and finally independent review/finalization. The initialized visual
minimum, section coverage, and figure start are immutable when the plan is
filled. Active SVG jobs are skipped while independent prose or research remains;
only when no such unit remains does the scheduler use the bounded `svg_wait`.
`finalize_publication` refuses completion while an SVG job is active. The host
does not persist a parallel workflow or summary database.

## Review and completion

`review_publication` first runs a fresh one-image ephemeral visual review for
each current planned preview. It hashes the compact assessment list, then starts
one separate ephemeral, fresh, read-only manuscript reviewer with no author
transcript and no image attachments. That reviewer receives the original task,
deterministic validator metrics, research call counts, the expected visual-audit
SHA-256, and the hash-bound one-image reports. It can audit task-to-contract loss
without creating an image-heavy request. `finalize_publication`
completes the durable root Goal only when:

1. the deterministic validator passes;
2. the reviewer reports the exact current article SHA-256;
3. the reviewer reports the exact visual-audit SHA-256 and confirms every
   current one-image audit passed;
4. verdict is `pass` and score reaches the project threshold;
5. no critical issue remains;
6. visual findings are present and every planned asset has valid evidence.

Deterministic validation also enforces maximum section and total length,
per-section long-sentence ratios, image-search receipts, figure count,
required-section coverage, contiguous numbering, and reviewer-role identity.

Run termination is also canonicalized in `run.json`: successful and failed runs
record `finished_at` plus `exit_code`, and the failure path refreshes the current
App Server Goal before persisting status. A capability change uses `restart`,
which clears stale terminal fields and starts a clean durable root over the same
three canonical workspace records.

## Compatibility baseline

The verified baseline is Codex CLI `0.151.0`, App Server experimental API,
Responses transport, and flat dynamic function tools. Upgrade by generating
the local App Server schema, running contract/domain tests, completing the
synthetic provider smoke, running the process-restart resume smoke, and
completing a real publication. Provider catalogs must not advertise Responses
tool types that the endpoint rejects; for iWorld Muse 1.2 the built-in
free-form `apply_patch` tool is omitted, while LongMDWriter dynamic tools remain
standard function tools. A successful terminal domain call is followed by an
App Server `turn/interrupt`; an interrupted turn counts as a completed logical
unit only when the runtime recorded that successful terminal call. Never
silently fall back to another control plane.
