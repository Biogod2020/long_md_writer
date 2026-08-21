# LongMDWriter: DSH-native loop

This directory is an out-of-tree DeepSeek Harness bundle that implements the first DSH-native publication path without removing the existing Python/Codex production workflow.

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

- DSH CLI: `0.1.0-rc.6`
- directly imported `@deepseek-ai/dsh-tools`: `0.1.0-rc.6`
- public seam contract inspected at source commit: `47f943859bef60e4160492346772ded9b24f765a`
- Node.js: 22 or newer
- Python: 3.11 or newer

The real CI profile smoke installs DSH `0.1.0-rc.6`, installs this bundle with `dsh plugin`, and verifies the composed Web profile through `--dump-config`. DSH remains a developer preview, so read [DSH_COMPATIBILITY.md](DSH_COMPATIBILITY.md) before upgrading.

## Install into the DSH Web profile

Install the exact DSH CLI release, then link this bundle into the persistent Web profile:

```bash
npm install --global @deepseek-ai/dsh@0.1.0-rc.6
cd long_md_writer
dsh plugin --profile web add ./dsh-native
dsh --profile web --dump-config
dsh --profile web
```

Use a dedicated DSH home or profile for this preview. The bundle overrides JSONL session storage to a versioned namespace:

```text
$DSH_HOME/sessions-longwriter/dsh-0.1.0-rc.6/
```

Open a new Web session in the desired publication workspace. Ask the root agent to create a publication and provide requirements or a project object. It should call `initialize_publication`, which creates the canonical files and an armed DSH Goal. The Goal Round Driver then continues the same Session until `finalize_publication` certifies completion.

After a process restart, reopen the persisted Session and ask it to continue. DSH intentionally disarms automatic goal activation on resume; the agent should call `resume_publication` to re-arm the existing Goal.

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

The visual path is `plan_visuals` → `svg_check` → `svg_submit` →
`svg_preflight` → inspect returned PNG with `read_image` → `svg_record_review`
→ Markdown reference in the planned section. The module never generates,
repairs, or visually judges with a model. It verifies SVG safety and structure,
measures text geometry with local CoreText, retains a PNG evidence asset, and
binds preflight/review receipts to the exact SVG and preview hashes. A failed
candidate remains historical; a corrected candidate must append an explicit
single-successor `supersedes_asset_id` revision. See
[docs/SVG_MODULE.md](../docs/SVG_MODULE.md) and the packaged
`svg-illustrator` Skill.
The package retains the pinned `@deepseek-ai/dsh-llm` dependency solely to
satisfy `@deepseek-ai/dsh-tools` peer requirements; the SVG module does not
import it or make model calls.

A turn may contain several model and tool steps for reading, searching, and reasoning. Only the terminal domain tools call DSH `concludeTurn()`, enforcing at most one manuscript commit per productive turn.

The generic model-facing goal, workflow, Ralph, shell, string-replace, and subagent tools are disabled in the bundle profile. Generic `write` and `edit` schemas may still be inherited with the upstream read tools, but a monotonic DSH guard denies every generic filesystem mutation. Canonical changes occur only through publication domain tools.

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
node --test test/project-store.test.js test/svg-core.test.js
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

This milestone is Markdown-first. It proves durable same-session iteration, atomic chunk commits, fresh reviewer delegation, evaluator-gated completion, update isolation, and a portable SVG evidence lane. SVG semantic correctness remains an explicit reviewer responsibility, but finalization now deterministically requires plan-to-section binding, an actual-geometry preflight, a retained preview, and a hash-bound review record. Self-contained HTML rendering, browser screenshots, and web image sourcing remain future domain tools.
