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

Current milestone: **M1 — Markdown-first**. The bundle includes a portable,
agent-drawn SVG lane with a planned section binding, CoreText geometry preflight,
retained PNG preview, and explicit hash-bound review evidence. Visual and
semantic judgment remain reviewer responsibilities rather than model-automated
claims (see `docs/SVG_MODULE.md`).

## Quick start

Pinned to DSH `0.1.0-rc.6`. Read `dsh-native/README.md` and
`dsh-native/DSH_COMPATIBILITY.md` first.

```bash
npm install --global @deepseek-ai/dsh@0.1.0-rc.6
cd long_md_writer
dsh plugin --profile web add ./dsh-native
dsh --profile web --dump-config
dsh --profile web
```

Open a Web session in the publication workspace and ask the root agent to
create a publication. It calls `initialize_publication` and the Goal Round
Driver continues the session until `finalize_publication` certifies completion.

Directory layout:

```text
dsh-native/
├── index.js                     # domain tool definitions and policy
├── lib/
│   ├── project-store.js         # atomic chunk store with injection guards
│   ├── validator-runner.js      # subprocess bridge to the Python validator
│   └── dsh-compat.js            # the only DSH-coupled adapter
├── svg/                         # SVG gate, CoreText preflight, evidence workflow, DSH adapter
├── skills/svg-illustrator/      # portable SVG drawing workflow
├── python/validate_publication.py  # deterministic acceptance authority
├── test/                        # domain and plugin-contract tests
├── cordis.patch.yml             # profile composition (session namespace, compaction)
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
