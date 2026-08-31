# LongMDWriter

LongMDWriter is a verifiable long-form Markdown publication system hosted by a
single Codex App Server. Codex owns durable threads, history, compaction,
clarification, recovery, and goals. LongMDWriter owns controlled publication
tools and three canonical records:

```text
project.json
article.md
assets/manifest.json
```

The root thread is read-only. It can modify the publication only through
`commit_chunk`, `revise_chunk`, and controlled visual tools. Completion is
possible only through `finalize_publication`, after deterministic validation
and a fresh SHA-bound reviewer thread both pass.

The initialized project contract carries both minimum and maximum length,
long-sentence limits, image-search requirements, and immutable visual count,
coverage, and figure-numbering rules. Image discovery and every visual check
leave provenance receipts in the existing manifest; no fourth workflow or
memory record is introduced.

Visual plans additionally state figure type, final publication width,
scientific claim/checks, and reading order. SVG candidates must pass CoreText-
based print-scale, density, balance, contrast, overlap, and connector-clearance
checks before a fresh one-image reviewer judges scientific and aesthetic
quality.

Bespoke SVGs can be delegated asynchronously. The root keeps writing while
fresh ephemeral illustrator threads work in a bounded pool. The first candidate
creates stable DOM ids; every revision must use the host's id-addressed
`svg_edit` tool against the retained champion. Coordinated edits may be sent as
one atomic batch and roll back together if any operation is invalid. Initial
and revision workers get dedicated read-only preflight tools that return exact
element ids and CoreText geometry; after a bounded amount of general shell work
the host steers the same active turn back to edit, preflight, and delivery
without revoking its read, network, or shell access. Locked passing checks cannot
regress, duplicate candidates are rejected, and repeated failures switch to a
simpler local layout edit instead of restarting from scratch.
Each illustrator gets broad read access, network access, routine shell commands,
and `on-request` approval with `auto_review` (the Codex “Approve for me” mode).
Its generic writes are confined to a retained per-attempt scratch directory;
canonical publication files and assets still change only through host-owned
domain boundaries.
Once a plan has been delegated, the root cannot fork that revision history with
direct `svg_submit`; it must collect the job's retained, review-bound champion.
Hidden text cannot satisfy a required label. Fragile mathematical typography
uses visible tspan composition plus a visually equivalent `aria-label`, so
subscripts and superscripts remain readable without weakening exact-label
evidence. The final publication validator applies the same visibility and
typographic-equivalence rule as SVG preflight.

## Quick start

Requirements: Codex CLI `0.151.0`, Node.js 22+, Python 3.11+, pnpm, and a
Responses-compatible provider credential.

```bash
cd codex-app-server
pnpm install --frozen-lockfile
pnpm test

# Either export IWORLD_API_KEY or put it in ignored codex-app-server/.env.
node cli.js start \
  --run ../runs/my-publication \
  --config config/iworld-muse12.json \
  --task ../runs/my-publication/task.txt
```

Resume the exact thread after interruption:

```bash
node cli.js resume --run ../runs/my-publication --config config/iworld-muse12.json
```

Every run retains `run.json`, `events.jsonl`, an isolated `.codex-home/`, and
the canonical workspace. Provider keys remain environment-only; the optional
local `.env` is Git-ignored and loaded without overriding an exported value.

## Tool surface

- publication: `initialize_publication`, `plan_visuals`,
  `publication_status`, `commit_chunk`, `revise_chunk`,
  `review_publication`, `finalize_publication`;
- visuals: `mermaid_submit`, `svg_check`, `svg_submit`, `svg_preflight`,
  `svg_delegate`, `svg_status`, `svg_wait`, `svg_collect`, `image_submit`,
  `inspect_visual`;
- optional search: the repository's `dsh-bing-search/` is mounted as a normal
  service behind `longwriter_search`, `longwriter_search_images`,
  `longwriter_open`, and `longwriter_find`; DSH itself is not used.

See [the architecture](docs/CODEX_APP_SERVER_ARCHITECTURE.md),
[Mermaid](docs/MERMAID_MODULE.md), and [SVG](docs/SVG_MODULE.md).

## Verification

```bash
cd codex-app-server
pnpm run check:imports
pnpm run test:app-server-contract
pnpm test
pnpm run benchmark:svg-quality -- --out /tmp/longwriter-svg-quality
pnpm run smoke:provider  # sends a synthetic string to the configured provider
pnpm run smoke:resume    # verifies thread, Goal, and tool recovery after restart
pnpm run smoke:search    # performs one real public-web search
```

`inspect_visual` never returns image bytes to the durable root thread. The host
opens one ephemeral read-only reviewer per retained PNG, sends exactly one
`localImage`, validates and stores the hash-bound result, then returns text-only
JSON. Final manuscript review receives those compact visual reports instead of
an unbounded batch of images. Any reviewer tool use is immediately interrupted
and rejected as evidence; the host allows at most two fresh-thread retries.

`inputs/` and `conductor/` are preserved source/history. Removed DSH,
Agents-SDK, and LangGraph implementations remain in Git history only.
