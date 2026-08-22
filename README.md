# LongWriter (Magnum Opus)

LongWriter is a harness-agnostic publication control plane for agent-generated
long-form Markdown. It keeps manuscript mutations atomic, assets auditable, and
finalization evaluator-gated without depending on one agent ecosystem.

```text
Skill                    how an agent should work
CLI / MCP                portable execution interfaces
@longwriter/core         state, revision, validation, evidence, finalization
optional adapters        DSH Goals and independent child-agent execution
```

## Repository layout

```text
packages/core       the product: publication kernel and deterministic gates
packages/cli        `longwriter` command-line interface
packages/mcp        stateless MCP stdio server
skills/longwriter   portable publication workflow
adapters/dsh        optional DeepSeek Harness integration
dsh-native          backwards-compatible DSH install path
```

The canonical publication files remain:

```text
project.json
article.md
assets/manifest.json
```

Core adds `.longwriter/` for a shared revision, cross-process lock, operation
ledger, finalization state, and independent-review receipts.

## Install and test

```bash
corepack enable
pnpm install --no-frozen-lockfile
pnpm check
pnpm test
```

## Use

```bash
longwriter init --workspace ./paper --project project.json
longwriter status --workspace ./paper
longwriter commit --workspace ./paper --section intro --chunk intro-01 \
  --file intro.md --expected-revision 1
longwriter validate --workspace ./paper
```

MCP clients can run `longwriter-mcp` over stdio and receive the same operations
as structured tools. The server does not run models or silently create
subagents; it emits and records explicit independent-review contracts.

DSH users may keep installing `./dsh-native`. That path now delegates to the
same Core rather than owning publication state.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/MIGRATION.md](docs/MIGRATION.md).
