# Magnum Opus

A bounded long-form publication system built on the OpenAI Agents SDK and Codex.

The Agents SDK is the delegation layer. Codex performs planning, section writing,
asset fulfillment, publishing, audit, repair, and verification inside disposable
workspace copies. Python owns state, locks, approvals, artifact promotion, browser
evidence, deterministic validation, and no-regression comparison.

## Why this architecture

The previous implementation encoded the publication process as a fine-grained
LangGraph graph and required model-generated search/replace patches. This version
uses five durable stages instead:

```text
plan -> draft -> assets -> publish -> qa
```

Each Codex task is bounded by an allowlist and executed in an isolated staging
workspace. A model response never constitutes acceptance. Physical artifacts are
validated and atomically promoted only after the filesystem contract and the
stage quality gate pass.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Set `OPENAI_API_KEY` or `CODEX_API_KEY`. The default manager model is
`gpt-5.6-sol`; the default workspace execution model is `gpt-5.3-codex`.

## Run

```bash
python main.py \
  --input inputs/prompt.txt \
  --reference inputs/source.md \
  --assets-dir inputs/assets \
  --mode html \
  --auto-approve \
  --output workspace
```

Markdown-only:

```bash
python main_markdown.py --intent "Write a rigorous technical guide" --auto-approve
```

Compare against a previous production workspace:

```bash
python main.py \
  --input inputs/prompt.txt \
  --baseline-workspace workspace/v18_comprehensive_run \
  --auto-approve
```

Validate any stage independently:

```bash
python -m src.orchestration.validate_cli \
  --workspace workspace/my-job \
  --stage qa \
  --mode html \
  --json
```

## Workspace contract

```text
workspace/<job-id>/
├── inputs/                     # immutable, control-plane-owned input copy
├── project_brief.md
├── plan.json
├── drafts/                     # immutable section drafts
├── md/                         # asset-resolved sections
├── assets/asset-manifest.json
├── final.md
├── final.html                  # HTML mode
├── qa/
│   ├── audit-findings.json
│   ├── browser_report.json
│   ├── render-desktop.png
│   └── render-mobile.png
├── qa_report.json
└── .magnum/                    # durable state and evidence logs
```

## Verification

```bash
pytest -q -m "not integration"
python -m playwright install chromium
pytest -q tests/integration/test_browser_probe.py
```

The credentialed Codex smoke test is intentionally opt-in through the GitHub
Actions `workflow_dispatch` input.

See [Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md), and
[Migration Notes](docs/MIGRATION.md).
