# LongMDWriter (Magnum Opus)

A bounded long-form publication system that runs as a **DeepSeek Harness (DSH)**
plugin. The current repository contains a single implementation: `dsh-native/`.

## What it is

A DSH-native publication loop. DSH owns conversation history, event
persistence, compaction, crash recovery, tool execution, goal continuation,
and child-agent lifecycle. The bundle owns only publication-domain policy and
three canonical workspace records:

```text
project.json          structural truth (objective, sections, quality and visual contracts)
article.md            the single canonical manuscript
assets/manifest.json  asset provenance, preflight, and review evidence truth
```

The loop: one durable root Session + one armed Goal. Each automatic Goal round
commits at most one manuscript chunk via `commit_chunk` / `revise_chunk`.
`finalize_publication` certifies completion only after deterministic validation
and a fresh independent reviewer both pass. The model cannot self-certify.

Current milestone: **M1 — Markdown-first**. The bundle uses DSH's native
clarification UI, image attachments, history, and compaction; it adds no intake
or manuscript-memory subsystem. The agent reads the complete `article.md`
before every commit or revision. Visuals use either a Mermaid-to-SVG tool or a
bespoke SVG lane, followed by the same CoreText preflight, retained PNG preview,
and hash-bound review evidence. See `docs/MERMAID_MODULE.md` and
`docs/SVG_MODULE.md`.

The repository's optional web and image search is the `dsh-bing-search/` Git
submodule. It is a separate MCP plugin: LongMDWriter permits its four
`mcp__web__*` tools when mounted but does not embed a machine-specific install
path. Set `LONGWRITER_DSH_SEARCH_BIN` to the installed executable's absolute
path to activate the bundle's optional MCP slot.

## Quick start

Pinned to DSH `0.1.1-rc.2`. Read `dsh-native/README.md` and
`dsh-native/DSH_COMPATIBILITY.md` first.

```bash
npm install --global @deepseek-ai/dsh@0.1.1-rc.2
cd long_md_writer
dsh plugin --profile web add ./dsh-native
dsh --profile web --dump-config
dsh --profile web
```

Open a Web session in the publication workspace and ask the root agent to
create a publication. Include raster reference images in the first message;
place other source files under `inputs/`. The agent infers what it can and uses
one native `ask_user_question` batch only for unresolved material choices. It
then calls `initialize_publication`, and the Goal Round Driver continues until
`finalize_publication` certifies completion.

Directory layout:

```text
dsh-native/
├── index.js                     # domain tool definitions and policy
├── lib/
│   ├── project-store.js         # atomic chunk store with injection guards
│   ├── validator-runner.js      # subprocess bridge to the Python validator
│   └── dsh-compat.js            # the only DSH-coupled adapter
├── svg/                         # SVG gate, CoreText preflight, evidence workflow, DSH adapter
├── mermaid/                     # bounded Mermaid, local renderer, source/SVG registration
├── skills/svg-illustrator/      # portable SVG drawing workflow
├── python/validate_publication.py  # deterministic acceptance authority
├── test/                        # domain and plugin-contract tests
├── cordis.patch.yml             # profile composition (session namespace, tool boundary, optional search)
└── examples/project.example.json
```

## Verification

```bash
cd dsh-native
node --test test/project-store.test.js
python3 -m unittest discover -s test -p 'test_validator.py'
```

CI (`.github/workflows/dsh-native.yml`) installs the pinned DSH release,
composes the bundle into a real DSH Web profile, and boots the Web server.

## History and comparison baseline

The Codex-era implementation (`src/orchestration/`, OpenAI Agents SDK + Codex
five-stage pipeline) and the earlier LangGraph multi-agent implementation were
removed from the working tree. Both remain in Git history.

**All comparisons in this repository use the pre-Codex (LangGraph) version as
the baseline** — i.e. "dsh vs codex-before" — per repository convention.

Materials that are preserved and protected:

- `inputs/` — source materials for publications
- `assets/` — publication asset library
- `conductor/` — historical development records (read-only archive)
