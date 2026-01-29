# AGENTS.md

Repository guidance for coding agents working on Magnum Opus HTML Agent (SOTA 2.0).

## Project Summary
Magnum Opus HTML Agent is a multi-agent system for generating technical Markdown/HTML with visual assets, QA loops, and design-system contracts. It uses LangGraph to orchestrate agents and a Gemini-compatible client for text+vision generation.

## Core Contracts (SSOT)
- Universal Asset Registry (UAR): assets.json holds asset metadata, semantic labels, and crop metadata for reuse.
- Full-Context Perception: Writer must receive manifest + brief + raw materials + UAR + completed sections + vision parts.
- Writer-Direct-Inject: Writer outputs `<img ...>` with crop metadata when a suitable asset exists; otherwise emits `:::visual`.
- Action Protocol: interactive behavior uses `:::script` and `data-controller` (see components.json when implemented).

## Key Workflows
- Streamlit GUI: `streamlit run app.py`
- CLI: `python main.py --input inputs/prompt.txt --output workspace/<job_id>/`
- With custom API: `python main.py --input inputs/prompt.txt --api-url http://localhost:8888/v1 --auth-token <token>`

## Primary Data Models
Defined in `src/core/types.py`:
- AgentState (workflow state)
- Manifest / SectionInfo (document plan)
- DesignTokens / StyleMapping (design contracts)
- AssetEntry / UniversalAssetRegistry (asset lifecycle)

## Agent Architecture
Agents live in `src/agents/` and typically:
1) Build prompts using AgentState inputs
2) Call GeminiClient (`generate_async` / `generate_structured_async`)
3) Update AgentState and return

Async agents (Writer, QA) should use non-blocking `await` patterns.

## Important Directories
- `src/core/`: shared types, validators, client, persistence, tools
- `src/agents/`: all agent implementations
- `src/orchestration/`: LangGraph workflow
- `workspace/<job_id>/`: run outputs (md, html, assets, logs)

## Validation and QA
- Static validators: `src/core/validators.py` (Markdown structure, HTML, LaTeX, namespace)
- Visual QA: `src/agents/visual_qa_agent.py` (headless browser screenshots + critic/fixer)

## Testing
- `python tests/test_system.py`
- `python tests/test_gemini_client.py`
- `python tests/test_qa_full_cycle.py`
- `python tests/test_sota2_integration.py`

## Debugging Tips
- UAR issues: inspect `assets.json` and `crop_metadata` values
- CSS/JS contract issues: inspect `style_mapping.json` and expected selectors
- Visual QA: check screenshot outputs in workspace job directories
