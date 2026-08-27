# LongMDWriter: DSH-native loop

This directory is the repository's only runtime implementation: an out-of-tree
DeepSeek Harness bundle for long-form Markdown publication.

The design is deliberately small:

```text
one root DSH Session
  + one durable Goal
  + Goal Round Driver
  + one atomic manuscript commit per turn
  + fresh read-only reviewer subagents
  + deterministic completion validation
```

DSH owns conversation history, event persistence, compaction, crash recovery, tool execution, goal continuation, and child-agent lifecycle. LongMDWriter owns only publication-domain policy, tools, validators, and three canonical workspace records:

```text
project.json
article.md
assets/manifest.json
```

## Compatibility baseline

The first public developer preview is pinned to:

- DSH CLI: `0.1.1-rc.2`
- directly imported `@deepseek-ai/dsh-tools`: `0.1.1-rc.2`
- public seam contract inspected at source commit: `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`
- Node.js: 22 or newer
- Python: 3.11 or newer

The real CI profile smoke installs DSH `0.1.1-rc.2`, installs this bundle with `dsh plugin`, and verifies the composed Web profile through `--dump-config`. DSH remains a developer preview, so read [DSH_COMPATIBILITY.md](DSH_COMPATIBILITY.md) before upgrading.

## Install into the DSH Web profile

Install the exact DSH CLI release, then link this bundle into the persistent Web profile:

```bash
npm install --global @deepseek-ai/dsh@0.1.1-rc.2
cd long_md_writer
dsh plugin --profile web add ./dsh-native
dsh --profile web --dump-config
dsh --profile web
```

Use a dedicated DSH home or profile for this preview. The bundle overrides JSONL session storage to a versioned namespace:

```text
$DSH_HOME/sessions-longwriter/dsh-0.1.1-rc.2/
```

Open a new Web session in the desired publication workspace. Ask the root agent to create a publication and provide requirements or a project object. It should call `initialize_publication`, which creates the canonical files and an armed DSH Goal. The Goal Round Driver then continues the same Session until `finalize_publication` certifies completion.

After a process restart, reopen the persisted Session and ask it to continue. DSH intentionally disarms automatic goal activation on resume; the agent should call `resume_publication` to re-arm the existing Goal.

## Start in the Web UI

The opening path deliberately uses DSH-native interaction rather than another
intake component:

1. Open the publication workspace in DSH Web and send the brief. Drag raster
   reference images into the same message when useful.
2. The root agent inspects the brief, all submitted images, and source files
   already present under the workspace `inputs/` directory.
3. It infers discoverable fields. Only a remaining user-owned choice or
   material ambiguity triggers one batched `ask_user_question` call.
4. It calls `initialize_publication` once and the normal Goal loop begins.

On the pinned DSH release, composer attachments are durable model-visible
PNG, JPEG, WebP, or GIF images. General documents are not composer
attachments; put PDFs, Markdown, text, tables, and other source files under
`inputs/` and let the agent read them in place. No LongMDWriter attachment
index or clarification state is added. A DSH image attachment is input
context, not automatically a registered publication asset.

Before every `commit_chunk` or `revise_chunk`, the agent must read the complete
current `article.md` from beginning to end in that same turn. DSH still owns
history and compaction; this is a writing policy, not a second memory system.

## Native tool surface

| Tool | Role | Ends root turn |
|---|---|---:|
| `initialize_publication` | Create canonical files and Goal | yes |
| `plan_visuals` | Set `project.json.visual_contract` before drawing figures | yes |
| `resume_publication` | Re-arm a resumed Goal | yes |
| `publication_status` | Read deterministic progress and article hash | no |
| `commit_chunk` | Append one coherent chunk atomically | yes |
| `revise_chunk` | Replace one existing chunk atomically | yes |
| `review_publication` | Run a fresh read-only reviewer subagent | yes |
| `finalize_publication` | Validate, independently review, and complete Goal | yes |
| `svg_check` | Deterministically inspect caller-supplied SVG source; never writes or calls a model | no |
| `svg_submit` | Re-check and append a planned SVG candidate through the asset store; dry runs do not write | no |
| `svg_preflight` | Retain a PNG preview and hash-bound CoreText geometry receipt for a planned SVG | no |
| `svg_record_review` | Append explicit pass/fail inspection evidence for that retained preview | no |
| `mermaid_submit` | Validate Mermaid, render locally, retain `.mmd`, and register its hash-bound SVG derivative; dry runs do not write | no |

For ordinary flowcharts, sequence diagrams, state machines, class diagrams,
and similar structured figures, the short path is `plan_visuals` →
`mermaid_submit` → `svg_preflight` → inspect the returned PNG with
`read_image` → `svg_record_review` → reference the returned SVG in Markdown.
`mermaid_submit` retains the editable `assets/mermaid/*.mmd` source and binds
the rendered SVG to its exact source hash.

For bespoke vector figures, use `plan_visuals` → `svg_check` → `svg_submit` →
the same preflight/review path. Neither module generates, repairs, or visually
judges with a model. They verify source safety and SVG structure,
measure text geometry with local CoreText, retain a PNG evidence asset, and
bind preflight/review receipts to the exact SVG and preview hashes. A failed
candidate remains historical; a corrected candidate must append an explicit
single-successor `supersedes_asset_id` revision. See
[docs/SVG_MODULE.md](../docs/SVG_MODULE.md) and the packaged
`svg-illustrator` Skill. Mermaid-specific details are in
[docs/MERMAID_MODULE.md](../docs/MERMAID_MODULE.md).
The package retains the pinned `@deepseek-ai/dsh-llm` dependency solely to
satisfy `@deepseek-ai/dsh-tools` peer requirements; the SVG module does not
import it or make model calls.

A turn may contain several model and tool steps for reading, searching, and reasoning. Only the terminal domain tools call DSH `concludeTurn()`, enforcing at most one manuscript commit per productive turn.

The bundle disables generic goal, workflow, Ralph, shell, string-replace, and
subagent tools at host composition. DSH's shipped Web preset can add
model-facing tools again per agent, so the bundle also installs a monotonic
global guard. Besides publication tools it permits read-only workspace tools,
DSH's native `ask_user_question`, the built-in `web_search`, and the four
`mcp__web__*` tools supplied by the optional repository search plugin. Tool
visibility is not an authority boundary; canonical changes and Goal completion
still occur only through publication domain tools.

## Repository search plugin

The user's search implementation is the root Git submodule
`dsh-bing-search/`. It supplies `mcp__web__search`,
`mcp__web__search_images`, `mcp__web__open`, and `mcp__web__find`. LongMDWriter
allows these tools but does not hard-code a machine-specific executable path,
so merely having the submodule does not mount it into DSH.

Install and mount it once by following
[`dsh-bing-search/INSTALL.md`](../dsh-bing-search/INSTALL.md). This bundle
already contains a disabled MCP slot, so the shortest setup is:

```bash
uv tool install --force git+https://github.com/Biogod2020/dsh-bing-search.git
uv tool dir --bin
export LONGWRITER_DSH_SEARCH_BIN=/ABSOLUTE/BIN/DIR/dsh-bing-search
dsh --profile web
```

The slot activates only when `LONGWRITER_DSH_SEARCH_BIN` names the absolute
executable. Leave it unset if the same MCP server is already mounted elsewhere.
Verify the four tool names and run one real search/open round trip. When the
slot is disabled, the publication policy falls back to DSH's `web_search`; no
second research state machine is introduced.

## Reviewer semantics

`review_publication` uses the DSH `spawn` in-process provider. The reviewer:

- gets a fresh child Session and no parent transcript;
- shares the parent workspace;
- receives a reviewer-specific persona;
- receives only read-oriented tools;
- must return a structured, SHA-bound verdict.

`finalize_publication` completes the Goal only when:

1. the deterministic Python validator passes;
2. the reviewer reports the same `article.md` SHA-256;
3. the reviewer verdict is `pass`;
4. the review score reaches `project.json`'s threshold;
5. no critical issue remains.

## Local verification

The domain store and validator do not require DSH packages and can be tested directly:

```bash
cd dsh-native
node --test test/project-store.test.js test/svg-core.test.js test/mermaid-core.test.js
python3 -m unittest discover -s test -p 'test_validator.py'
```

With npm access available, verify the pinned public package import as well:

```bash
corepack enable
pnpm install --no-frozen-lockfile
pnpm run check:imports
pnpm test
```

## Current scope

This milestone is Markdown-first. It proves durable same-session iteration,
atomic chunk commits, native clarification and image intake, fresh reviewer
delegation, evaluator-gated completion, optional repository search, a portable
SVG evidence lane, and a Mermaid-to-SVG lane. SVG semantic correctness remains
an explicit reviewer responsibility. Self-contained HTML rendering, browser
screenshots, generative imagery, and controlled download/licence registration
for searched images remain outside the current scope.
