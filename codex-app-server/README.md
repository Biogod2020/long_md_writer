# LongMDWriter Codex App Server host

This directory is the repository's only runtime implementation. It contains a
small line-delimited JSON-RPC client for `codex app-server --stdio`, the
publication Goal driver, dynamic domain tools, an independent reviewer-thread
adapter, and the runtime-independent publication core.

## Run contract

```text
one durable root thread
  + one measurable publication Goal
  + one terminal publication action per turn
  + read-only Codex sandbox
  + controlled domain mutations in the client
  + bounded asynchronous ephemeral SVG-worker threads
  + id-addressed in-memory svg_edit revisions against a retained champion
  + one-image diagnostic reviewers for failed SVG preflights
  + one-image ephemeral visual-reviewer threads
  + one text-only final reviewer thread
  + deterministic finalize gate
```

Each run uses its own `.codex-home` so global Codex plugins and MCP servers
cannot alter provider tool schemas or permissions. The verified baseline is
Codex CLI `0.151.0`; the host rejects a mismatched version.

## CLI

```bash
node cli.js start --run RUN_DIR --config config/iworld-muse12.json --task TASK_FILE
node cli.js resume --run RUN_DIR --config config/iworld-muse12.json
node cli.js resume --run RUN_DIR --config config/iworld-muse12.json --instruction-file RUN_DIR/review-fix.txt
node cli.js restart --run RUN_DIR --config config/iworld-muse12.json
node cli.js status --run RUN_DIR
```

Use repeated `--input FILE` or `--image FILE` arguments when preparing a new
run. Inputs are copied under `workspace/inputs/` with SHA-256 receipts, and
images are also sent as native App Server local-image input blocks. If the task
already states a measurable contract, the writer skips clarification and
initializes from it. It only asks one native clarification question when a
user-owned choice is still missing. `--non-interactive` refuses to guess.

The default iWorld config uses `muse-spark-1.2`, `xhigh` reasoning, Responses
transport, a read-only sandbox, and environment variable `IWORLD_API_KEY`.
For local use, an ignored `codex-app-server/.env` may define that variable;
CLI and smoke entrypoints load it without overriding an already-exported value.
Repository search is exposed as four flat App Server dynamic function tools.
The adapter invokes the existing `dsh-bing-search` service through its pinned
`uv.lock`. This avoids Codex's provider-specific MCP namespace encoding while
retaining the same search, image search, open, and find implementation.
The run config may require a minimum number of successful search, image-search,
and source-open calls before `plan_visuals`. Successful call counts are
retained in `run.json`, while every successful image search automatically adds
a compact hash-bound candidate receipt to `assets/manifest.json`. The exact
request/result stream remains in `events.jsonl`. Image-search receipts are
research traces the host records automatically. The writer calls search and
visual tools directly while writing. `image_submit` downloads a public image
URL and registers it under `assets/photos/`; the manuscript may still cite only
that local path, never a remote URL. The visual-plan minimum is a floor.

For a bespoke planned SVG, `svg_delegate` starts a bounded background job and
returns immediately, so the durable root can continue an independent prose or
research unit. The initial fresh worker creates a complete SVG with stable DOM
ids. Every revision runs in another fresh ephemeral thread and receives only a
narrow `svg_edit` tool backed by the host's in-memory champion draft. The tool
edits one target id at a time and validates the whole transaction; revision
output cannot replace the full source. Passing preflight, labels, scientific
checks, and design checks become monotonic locks. Regressing or duplicate
challengers cannot replace the champion; next-round feedback remains bound to
the champion instead of a rejected draft. Repeated stagnation triggers a
simpler local layout edit, and attempts/concurrency are bounded by `svg_workers` config.
SVG illustrator threads use `workspace-write`, `on-request`, and `auto_review`
(the “Approve for me” preset). Each turn enables network access and routine
shell execution, with broad filesystem reads and exactly one generic writable
root at `RUN/svg-workers/JOB/attempt-N`. These retained scratch directories are
for references, calculations, and local rendering experiments; canonical
publication writes still pass only through the host's initial-candidate return
or the in-memory `svg_edit` boundary. The policy explicitly removes the
otherwise implicit `/tmp` and `$TMPDIR` writable exceptions.
The controlled pool accepts one to six concurrent SVG jobs; the default remains
two so ordinary publication runs do not unexpectedly fan out. Continuation
prompting fills free SVG slots before prose, one bounded delegation per turn;
once the pool is full, the root resumes independent writing or research.
The host treats a successful `svg_delegate` as a terminal turn unit and
interrupts that turn, preventing a provider from idling through unrelated tool
calls after the asynchronous job has already started.
If one plan exhausts its bounded budget while delegated peers are still active,
the root waits for those peers to reach terminal states before the host fails the
run. This preserves complete batch evidence instead of cancelling unrelated work.
Job state lives in `run.json` for restart recovery, not in a new canonical
workspace record.

When an SVG candidate fails deterministic preflight, the host sends its bound
PNG to one fresh tool-free Muse thread in diagnostic mode. Pixel-grounded
findings are placed before the bounded geometry findings in the next champion
edit prompt. They are scheduling feedback only: diagnostics do not append a
`visual_reviews` receipt, raise the candidate's acceptance tier, lock a pass,
or permit citation. Minimum-font findings also state that the right-hand value
is the required SVG-unit floor and overlap must not be repaired by shrinking
text.

New runs also record a SHA-256 fingerprint and file count for the complete
runtime/config source set in `run.json` and `RUN.md`, so an uncommitted checkout
can still be tied to the exact host implementation that produced the output.

Continuation prompts are derived from the three canonical workspace records.
The host completes gated research and the full visual plan before prose, then
fills under-length sections, tightens sections that exceed length or long-
sentence ceilings, completes each current visual's
asset/preflight/independent-check/citation chain, and only then asks for independent
review and finalization. Figure numbering is contiguous from the initialized
start and the plan tool cannot weaken initialized count or section-coverage
requirements.

After an independent publication review, the host retains a compact SHA-bound
review summary in `run.json` for scheduling only. A passing review of the
current article advances the next root turn to `finalize_publication`; a failed
review requires a manuscript revision before another review. This metadata is
not a fourth canonical publication record.

`review_publication` first runs the deterministic validator and returns its
failures immediately when any hard gate fails. It does not spend provider calls
on fresh per-image or manuscript review until length, structure, provenance,
and other deterministic requirements are already eligible. The next-unit
scheduler checks both per-section and total-length ceilings; when only the total
is high, it selects a safely reducible chunk and states the minimum word
reduction before review can be retried.

The host's single-image model boundary has acceptance and diagnostic modes.
The root-visible `inspect_visual` tool still resolves only a current asset with
a passing preflight and may append acceptance evidence. The internal SVG
diagnostic mode may inspect a failed preflight's bound preview but can return
feedback only. Both start an ephemeral read-only reviewer, send exactly one
`localImage`, validate every returned id/hash and required label, and
unsubscribe the ephemeral thread. Only acceptance mode appends an
`independent_visual_review` receipt and returns text-only JSON to the durable
root. Exact repeat acceptance inspections
reuse a receipt only when the preview hash and reviewer model/config hash match.
The turn receives a dedicated tool-free collaboration instruction. If the
reviewer nevertheless starts any shell, file, web, MCP, image-view, or agent
tool, the host interrupts that turn, rejects it as evidence, and permits at
most two fresh-thread retries. The cache hash includes the visual-review policy,
tool-free instruction, and output schema. A failed
inspection advances the scheduler to an append-only replacement asset instead
of repeatedly reinspecting unchanged bytes. A fail verdict without at least one
actionable finding is also rejected and retried. Photo requirements identify visible
subjects/details; diagram requirements remain literal readable text labels.
The final reviewer receives fresh per-image reports and no image attachments, so
neither root history nor final-review payload grows with accumulated image bytes.

Schema-v2 visual plans also bind each figure to a type, single- or double-column
publication width, falsifiable scientific claim, explicit scientific checks,
and reading order. SVG preflight measures the 8 pt print-scale floor with
CoreText and rejects excessive text, too many font tiers, unbalanced canvas
use, weak contrast, overlap, and line/polyline connectors that enter a text
safety margin. More than 100 findings are compacted deterministically across
issue categories with explicit total and omitted counts, preserving bounded
but actionable feedback. The independent reviewer separately checks scientific
completeness, semantic visual grammar, text economy, spacing, palette/dual
encoding, reading order, and aesthetics; deterministic geometry never claims
to prove those judgments.

On completion or failure, `run.json` records `finished_at` and `exit_code`; a
failed turn also refreshes the App Server Goal before recording the final state.

Use `resume` after an ordinary process interruption. Use `restart` only after
a host capability or dynamic-tool contract change: it retains the canonical
workspace and records the replaced thread id in `run.json`, but creates a new
durable thread because App Server dynamic tools are fixed at thread start.
`--instruction-file` is the narrow human-review seam: its absolute path,
SHA-256, and application time are retained in `run.json`, while the requested
change must still go through normal domain tools and validation.

## Security and approvals

The writer uses `approvalPolicy: never`. Domain tools need no Codex approval
because they execute in the client and apply their own validation. The host
declines command, file-change, permission, and MCP-elicitation callbacks. This
is deliberately stricter than auto-approving generic writes: the model can
inspect all source and manuscript state but cannot route around the canonical
store.

The SVG illustrator is the deliberate exception to the root's execution
profile. It uses `workspace-write + on-request + auto_review`, enables network
access, and may run shell commands. Its writable roots contain only its isolated
scratch directory, never the canonical workspace. Visual reviewers and the
final manuscript reviewer remain read-only and tool-free where specified.
The repository contract explicitly treats normal worker reads, network calls,
shell commands, and scratch writes as valid worker activity rather than applying
the root writer's read-only rule to them.

## Verification

```bash
pnpm run check:imports
pnpm run test:app-server-contract
pnpm test
pnpm run benchmark:svg-quality -- --out /tmp/longwriter-svg-quality
pnpm run smoke:provider
pnpm run smoke:resume
pnpm run smoke:search
```

The provider smoke sends only `IWORLD_CODEX_OK` and verifies a real dynamic
tool round trip. The resume smoke sends only `PHASE_ONE` and `PHASE_TWO`, then
restarts App Server and verifies that the durable thread, active Goal, and
dynamic tool registry were restored. Both require the configured credential
environment variable.

The search smoke performs one real public-web query through the flat search
bridge and checks that at least one non-poor result is returned.
